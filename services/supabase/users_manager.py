# Standard imports
import logging
from datetime import datetime

# Third Party imports
import stripe
from supabase import Client

# Local imports
from config import DEFAULT_TIME, STRIPE_FREE_TIER_PRICE_ID, TZ
from services.stripe.customer import (
    get_subscription,
    get_request_count_from_product_id_metadata,
    subscribe_to_free_plan,
)
from utils.handle_exceptions import handle_exceptions


class UsersManager:
    """Manager for all user related operations"""

    def __init__(self, client: Client) -> None:
        self.client: Client = client

    @handle_exceptions(default_return_value=None, raise_on_error=False)
    def create_user(self, user_id: int, user_name: str, installation_id: int) -> None:
        """Creates an account for the user in the users table"""
        self.client.table(table_name="users").upsert(
            json={
                "user_id": user_id,
                "user_name": user_name,
            }
        ).execute()

        self.client.table(table_name="user_installations").insert(
            json={
                "user_id": user_id,
                "installation_id": installation_id,
            }
        ).execute()

    # Check if user has a seat in an org or can be given a seat
    @handle_exceptions(default_return_value=True, raise_on_error=False)
    def is_user_eligible_for_seat_handler(
        self, user_id: int, installation_id: int, quantity: int
    ) -> bool:
        # Check is user already assigned to a seat
        data, _ = (
            self.client.table(table_name="user_installations")
            .select("*")
            .eq(column="user_id", value=user_id)
            .eq(column="installation_id", value=installation_id)
            .execute()
        )
        if data[1] and data[1][0]["is_user_assigned"]:
            return True

        # Check if a seat is available for a user
        assigned_users, _ = (
            self.client.table(table_name="user_installations")
            .select("*")
            .eq(column="installation_id", value=installation_id)
            .eq(column="is_user_assigned", value=True)
            .execute()
        )
        if len(assigned_users[1]) >= quantity:
            return False

        # Set user as assigned in db
        self.client.table(table_name="user_installations").update(
            json={"is_user_assigned": True}
        ).eq(column="user_id", value=user_id).eq(
            column="installation_id", value=installation_id
        ).execute()
        return True

    @handle_exceptions(default_return_value=None, raise_on_error=True)
    def parse_subscription_object(
        self,
        subscription: stripe.ListObject[stripe.Subscription],
        user_id: int,
        installation_id: int,
        customer_id: str,
        user_name: str,
        owner_id: int,
        owner_name: str,
    ) -> tuple[int, int, str]:
        """Parsing stripe subscription object to get the start date, end date and product id of either a paid or free tier customer subscription"""
        if len(subscription.data) > 2:
            raise ValueError(
                "There are more than 2 active subscriptions for this customer. This is a check when we move to multiple paid subscriptions."
            )

        free_tier_start_date = 0
        free_tier_end_date = 0
        free_tier_product_id = ""
        # return the first paid subscription if found, if not return the free one found
        for sub in subscription.data:
            # Iterate over the items, there should only be one item, but we are iterating just in case
            for item in sub["items"]["data"]:
                # Check if item is non-free tier
                if item["price"]["id"] == STRIPE_FREE_TIER_PRICE_ID:
                    # Save free tier info to return just in case paid tier is not found
                    free_tier_start_date = sub.current_period_start
                    free_tier_end_date = sub.current_period_end
                    free_tier_product_id = item["price"]["product"]
                    continue

                # Check if user has or can be assigned a seat
                if self.is_user_eligible_for_seat_handler(
                    user_id=user_id,
                    installation_id=installation_id,
                    quantity=item["quantity"],
                ):
                    return (
                        sub["current_period_start"],
                        sub["current_period_end"],
                        item["price"]["product"],
                    )

        if (
            free_tier_start_date == 0
            or free_tier_end_date == 0
            or free_tier_product_id == ""
        ):
            # Customer should alawys have at least a free tier subscription, set by this codebase on installation webhook from github
            subscribe_to_free_plan(
                customer_id=customer_id,
                user_id=user_id,
                user_name=user_name,
                owner_id=owner_id,
                owner_name=owner_name,
                installation_id=installation_id,
            )
            subscription = get_subscription(
                customer_id=customer_id,
            )
            return self.parse_subscription_object(
                subscription=subscription,
                user_id=user_id,
                installation_id=installation_id,
                customer_id=customer_id,
                user_name=user_name,
                owner_id=owner_id,
                owner_name=owner_name,
            )
        # Return from Free Tier Subscription if there is no paid subscription object
        return free_tier_start_date, free_tier_end_date, free_tier_product_id

    @handle_exceptions(default_return_value=(1, 1, DEFAULT_TIME), raise_on_error=False)
    def get_how_many_requests_left_and_cycle(
        self,
        user_id: int,
        installation_id: int,
        user_name: str,
        owner_id: int,
        owner_name: str,
    ) -> tuple[int, int, datetime]:
        data, _ = (
            self.client.table(table_name="installations")
            .select("owner_id, owners(stripe_customer_id)")
            .eq(column="installation_id", value=installation_id)
            .execute()
        )
        if (
            not data
            or not data[1]
            or not data[1][0]
            or not data[1][0]["owners"]
            or not data[1][0]["owners"]["stripe_customer_id"]
            or not isinstance(data[1][0]["owners"]["stripe_customer_id"], str)
        ):
            logging.error(
                "No Stripe Customer ID found for installation %s user %s. This has to due with fetching from supabase.",
                installation_id,
                user_id,
            )
            return (1, 1, DEFAULT_TIME)

        stripe_customer_id: str = data[1][0]["owners"]["stripe_customer_id"]

        subscription = get_subscription(
            customer_id=stripe_customer_id,
        )

        start_date_seconds, end_date_seconds, product_id = (
            self.parse_subscription_object(
                subscription=subscription,
                user_id=user_id,
                installation_id=installation_id,
                customer_id=stripe_customer_id,
                user_name=user_name,
                owner_id=owner_id,
                owner_name=owner_name,
            )
        )

        request_count = get_request_count_from_product_id_metadata(product_id)

        start_date = datetime.fromtimestamp(timestamp=start_date_seconds, tz=TZ)
        end_date = datetime.fromtimestamp(timestamp=end_date_seconds, tz=TZ)

        # Calculate how many completed requests for this user account
        data, _ = (
            self.client.table("usage")
            .select("*")
            .gt("created_at", start_date)
            .eq("user_id", user_id)
            .eq("installation_id", installation_id)
            .eq("is_completed ", True)
            .execute()
        )
        requests_left = request_count - len(data[1])

        return (
            requests_left,
            request_count,
            end_date,
        )

    @handle_exceptions(default_return_value=False, raise_on_error=False)
    def user_exists(self, user_id: int) -> bool:
        """Check if user exists in users table"""
        data, _ = (
            self.client.table(table_name="users")
            .select("*")
            .eq(column="user_id", value=user_id)
            .execute()
        )
        if len(data[1]) > 0:
            return True
        return False
    
    @handle_exceptions(default_return_value=None, raise_on_error=False)
    def query_user(self, **kwargs) -> dict:
        """Query a user record from the users table based on id, user_name, user_id, or email"""
        valid_keys = {"id", "user_name", "user_id", "email"}
        filters = {k: v for k, v in kwargs.items() if k in valid_keys and v is not None}
        if not filters:
            logging.error("No valid filters provided for querying user.")
            return None
        # Build and execute query
        query = self.client.table("users").select("*")
        for key, value in filters.items():
            query = query.eq(column=key, value=value)
        # Execute query and return first matching record, if any
        data, _ = query.execute()
        return data[1][0] if data and data[1] else None

    @handle_exceptions(default_return_value=None, raise_on_error=False)
    def query_installation(self, sort_column: str|None=None, case_sensitive: bool=False, **kwargs) -> dict:
        """Query an installation record from the installations table based on jira_workspace_id, installation_id, owner_name, owner_id, repo_name, and/or uninstalled_at"""
        valid_keys = {"jira_workspace_id", "installation_id", "owner_name", "owner_id", "repo_name", "uninstalled_at"}
        filters = {k: v for k, v in kwargs.items() if k in valid_keys}
        if not filters:
            logging.error("No valid filters provided for querying installation.")
            return None
        
        # Define numeric fields that should always use eq operator
        numeric_fields = {"owner_id", "installation_id"}
        query = self.client.table("installations").select("*")
        for key, value in filters.items():
            if value is None:
                query = query.is_(column=key, value=None)
            elif key in numeric_fields:
                # Always use eq for numeric fields
                query = query.eq(column=key, value=value)
            elif isinstance(value, str) and not case_sensitive:
                query = query.ilike(key, value)
            else:
                query = query.eq(column=key, value=value)
         
        if sort_column:
            query = query.order(column=sort_column, desc=True)
        
        data, _ = query.execute()
        return data[1][0] if data and data[1] else None
