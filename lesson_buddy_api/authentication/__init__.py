from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    RemovalPolicy
)
from constructs import Construct

class AuthenticationStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.user_pool = cognito.UserPool(
            self,
            "LessonBuddyUserPool",
            user_pool_name="lesson-buddy-user-pool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                phone=True
            ),
            auto_verify=cognito.AutoVerifiedAttrs(
                email=True,
                phone=True
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                phone_number=cognito.StandardAttribute(required=True, mutable=True)
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_AND_PHONE_WITHOUT_MFA,
            removal_policy=RemovalPolicy.DESTROY # Or RETAIN, depending on preference
        )

        self.user_pool_client = cognito.UserPoolClient(
            self,
            "LessonBuddyUserPoolClient",
            user_pool=self.user_pool,
            user_pool_client_name="lesson-buddy-app-client"
        )
