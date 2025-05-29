from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    aws_apigateway as apigw, # Import apigateway
    RemovalPolicy
)
from constructs import Construct

class Authentication(Construct):
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

        # Define callback and logout URLs to be used
        # These are placeholders and should be updated by the user for their actual frontend
        defined_callback_urls = ["https://localhost/callback"]
        defined_logout_urls = ["https://localhost/logout"]

        self.user_pool_client = cognito.UserPoolClient(
            self,
            "LessonBuddyUserPoolClient",
            user_pool=self.user_pool,
            user_pool_client_name="lesson-buddy-app-client",
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True # Often used for SPAs
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                    cognito.OAuthScope.COGNITO_ADMIN # If admin operations are needed through API
                ],
                callback_urls=defined_callback_urls,
                logout_urls=defined_logout_urls
            )
        )

        # Store the first callback and logout URL for easy access by other constructs
        # These are kept in case the client uses direct OAuth endpoints, but not used by API Gateway anymore
        self.app_client_callback_url = defined_callback_urls[0]
        self.app_client_logout_url = defined_logout_urls[0]

        # Create a Cognito User Pool Authorizer for API Gateway (RestApi)
        self.authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "LessonBuddyCognitoAuthorizer",
            cognito_user_pools=[self.user_pool]
        )
