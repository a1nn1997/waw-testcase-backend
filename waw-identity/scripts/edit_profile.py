"""
CLI tool to create or update a user profile via the IdentityService gRPC API.
"""

import argparse
import uuid
from datetime import datetime, timezone

import grpc
from dotenv import load_dotenv

import identity_pb2
import identity_pb2_grpc


# Load environment variables
load_dotenv()

# gRPC server address
GRPC_SERVER = "localhost:50051"


class ProfileUpdater:
    """Performs gRPC calls to fetch and update user profiles."""

    def __init__(self, grpc_server: str):
        self.channel = grpc.insecure_channel(grpc_server)
        self.stub = identity_pb2_grpc.IdentityServiceStub(self.channel)

    def get_existing_profile(self) -> identity_pb2.UserProfile:
        """Fetch the existing profile, or return an empty one."""
        try:
            return self.stub.GetProfile(identity_pb2.Empty())
        except grpc.RpcError as error:
            print(f"Error fetching profile: {error.details()}")
            return identity_pb2.UserProfile()

    def update_profile(
        self, profile: identity_pb2.UserProfile
    ) -> identity_pb2.UserProfile:
        """Send an UpdateProfile request and return the server response."""
        try:
            delta = identity_pb2.ProfileDelta(profile=profile)
            return self.stub.UpdateProfile(delta)
        except grpc.RpcError as error:
            print(f"Error updating profile: {error.details()}")
            return identity_pb2.UserProfile()


def create_or_update_profile(
    existing: identity_pb2.UserProfile, args: argparse.Namespace
) -> identity_pb2.UserProfile:
    """Build a UserProfile from CLI args, using existing values as needed."""
    now = datetime.now(timezone.utc).isoformat()
    user_id = args.id or existing.id or str(uuid.uuid4())
    created = existing.created_at or now

    return identity_pb2.UserProfile(
        id=user_id,
        name=args.name,
        email=args.email,
        phone=args.phone,
        created_at=created,
        updated_at=now,
    )


def parse_arguments() -> argparse.Namespace:
    """Define and parse command-line flags."""
    parser = argparse.ArgumentParser(
        description="Update or create a user profile via gRPC"
    )
    parser.add_argument(
        "--id", help="User ID (optional; autogenerated if omitted)"
    )
    parser.add_argument(
        "--name", required=True, help="User full name"
    )
    parser.add_argument(
        "--email", required=True, help="User email address"
    )
    parser.add_argument(
        "--phone",
        default="",
        help="Phone number (optional)",
    )
    return parser.parse_args()


def print_profile(response: identity_pb2.UserProfile) -> None:
    """Display the updated profile fields."""
    print("✅ Profile updated:")
    print(f"  id:         {response.id}")
    print(f"  name:       {response.name}")
    print(f"  email:      {response.email}")
    print(f"  phone:      {response.phone}")
    print(f"  created_at: {response.created_at}")
    print(f"  updated_at: {response.updated_at}")


def main() -> None:
    """Entry point: parse args, fetch, update, and print profile."""
    args = parse_arguments()
    updater = ProfileUpdater(GRPC_SERVER)
    existing = updater.get_existing_profile()
    profile = create_or_update_profile(existing, args)
    response = updater.update_profile(profile)
    print_profile(response)


if __name__ == "__main__":
    main()
