"""Manager for all user related operations"""

from typing import Union
import datetime
import logging
from services.stripe.customer import (
    get_subscription,
    get_request_count_from_product_id_metadata,
)
from config import (
    STRIPE_FREE_TIER_PRICE_ID,
)
from supabase import Client


class UsersManager:
    def __init__(self, client: Client) -> None:
        self.client = client

    def create_user(self, user_id: int, user_name: str, installation_id: int) -> None:
        try:
            self.client.table(table_name="users").insert(
                json={
                    "user_id": user_id,
                    "user_name": user_name,
                    "installation_id": installation_id,
                }
            ).execute()
        except Exception as err:
            logging.error(f"create_user {err}")

    def is_user_eligible_for_seat_handler(
        self, user_id: int, installation_id: int, quantity: int
    ) -> bool:
        try:
            # Check is user already assigned to a seat
            data, _ = (
                self.client.table(table_name="users")
                .select("*")
                .eq(column="user_id", value=user_id)
                .eq(column="installation_id", value=installation_id)
                .execute()
            )
            if data[1][0]["is_user_assigned"]:
                return True
            else:
                # Check if a seat is available for a user
                assigned_users, _ = (
                    self.client.table(table_name="users")
                    .select("*")
                    .eq(column="installation_id", value=installation_id)
                    .eq(column="is_user_assigned", value=True)
                    .execute()
                )
                if len(assigned_users[1]) >= quantity:
                    return False
                else:
                    # Set user as assigned in db
                    self.client.table(table_name="users").update(
                        json={"is_user_assigned": True}
                    ).eq(column="user_id", value=user_id).eq(
                        column="installation_id", value=installation_id
                    ).execute()
            return True
        except Exception as err:
            logging.error(f"is_user_eligible_for_seat_handler {err}")
            return True

    def parse_subscription_object(
        self, subscription, user_id, installation_id
    ) -> Union[int, int, str]:
        try:
            free_tier_start_date = 0
            free_tier_end_date = 0
            free_tier_product_id = ""
            # Find all active subscriptions, return the first paid subscription if found, if not return the free one found
            for sub in subscription["data"]:
                if sub.status == "active":
                    for item in sub["items"]["data"]:
                        if item["price"]["active"] is True:
                            if item["price"][
                                "id"
                            ] != STRIPE_FREE_TIER_PRICE_ID and self.is_user_eligible_for_seat_handler(
                                user_id=user_id,
                                installation_id=installation_id,
                                quantity=item["quantity"],
                            ):
                                # Return from Paid Subscription if we find one
                                return (
                                    sub.current_period_start,
                                    sub.current_period_end,
                                    item["price"]["product"],
                                )
                            else:
                                free_tier_start_date = sub.current_period_start
                                free_tier_end_date = sub.current_period_end
                                free_tier_product_id = item["price"]["product"]
            if (
                first_tier_start_date == 0
                or first_tier_end_date == 0
                or first_tier_product_id == ""
            ):
                raise Exception("No active subscription found")
            # Return from Free Tier Subscription if there is no paid subscription object
            return free_tier_start_date, free_tier_end_date, free_tier_product_id
        except Exception as e:
            print("ERROR: ", e)
            logging.error(f"parse_subscription_object {e}")
            raise

    def get_how_many_requests_left_and_cycle(
        self, user_id: int, installation_id: int
    ) -> tuple[int, int, str]:
        try:
            data, _ = (
                self.client.table(table_name="installations")
                .select("owner_id, owners(stripe_customer_id)")
                .eq(column="installation_id", value=installation_id)
                .execute()
            )

            stripe_customer_id = data[1][0]["owners"]["stripe_customer_id"]

            if stripe_customer_id:
                subscription = get_subscription(
                    customer_id=stripe_customer_id,
                )
                start_date_seconds, end_date_seconds, product_id = (
                    self.parse_subscription_object(
                        subscription=subscription,
                        user_id=user_id,
                        installation_id=installation_id,
                    )
                )

                request_count = get_request_count_from_product_id_metadata(product_id)

                start_date = datetime.datetime.fromtimestamp(start_date_seconds)
                end_date = datetime.datetime.fromtimestamp(end_date_seconds)

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
                requests_made_in_this_cycle = len(data[1])

                return requests_left, requests_made_in_this_cycle, end_date

            logging.error(
                "No Stripe Customer ID found for installation %s user %s",
                installation_id,
                user_id,
            )
            raise
        except Exception as err:
            logging.error(f"get_how_many_requests_left_and_cycle {err}")
            # TODO Send comment to user issue
            return "N/A", "N/A", "N/A"

    def user_exists(self, user_id: int, installation_id: int) -> None:
        try:
            data, _ = (
                self.client.table(table_name="users")
                .select("*")
                .eq(column="user_id", value=user_id)
                .eq(column="installation_id", value=installation_id)
                .execute()
            )
            if len(data[1]) > 0:
                return True
            return False
        except Exception as err:
            logging.error(f"user_exists {err}")
