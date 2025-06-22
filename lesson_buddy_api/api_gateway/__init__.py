from aws_cdk import (
    aws_apigateway as apigw,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_iam as iam, # Added for potential Step Functions role if needed for sync
    aws_cognito as cognito # Added for Cognito types
)
from constructs import Construct
import json

class LessonBuddyApiGateway(Construct):
    def __init__(self, scope: Construct, id: str,
                 generate_chapter_sfn: sfn.IStateMachine,
                 generate_course_plan_function: _lambda.Function,
                 get_course_list_function: _lambda.Function,
                 get_lesson_content_function: _lambda.Function,
                 get_lesson_plan_function: _lambda.Function,
                 check_chapter_generation_status_function: _lambda.Function, # Added new function
                 # Authentication parameters
                 cognito_authorizer: apigw.CognitoUserPoolsAuthorizer,
                 user_pool_client: cognito.UserPoolClient, 
                 get_user_info_function: _lambda.Function,
                 # Server-side auth flow functions
                 auth_signup_function: _lambda.Function, # Added
                 auth_signin_function: _lambda.Function, # Added
                 auth_verify_code_function: _lambda.Function, # Added
                 auth_resend_verification_code_function: _lambda.Function, # Added
                 auth_refresh_token_function: _lambda.Function, # Added
                 get_multiple_choice_questions_function: _lambda.Function, # Added for new endpoint
                 get_flashcards_function: _lambda.Function, # Added for flashcards endpoint
                 get_image_data_function: _lambda.Function, # Added for new endpoint
                 delete_course_function: _lambda.Function, # Added for new endpoint
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Define the API Gateway
        api = apigw.RestApi(self, "LessonBuddyApi",
                            rest_api_name="lesson-buddy-api", # Matching image context
                            description="API for Lesson Buddy services.",
                            default_cors_preflight_options=apigw.CorsOptions(
                                allow_origins=apigw.Cors.ALL_ORIGINS,
                                allow_methods=apigw.Cors.ALL_METHODS,
                                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key", "X-Amz-Security-Token"]
                            ))

        # Integration for /generate-chapter (Step Function)
        # This uses StartExecution, which is asynchronous.
        # The API will return immediately after starting the Step Function.
        # We will use AwsIntegration for explicit control.

        # Create an IAM role for API Gateway to invoke Step Functions
        api_gw_sfn_role = iam.Role(
            self, "ApiGatewayStepFunctionsRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com")
        )

        # Add a policy to the role to allow starting execution of the state machine
        api_gw_sfn_role.add_to_policy(iam.PolicyStatement(
            actions=["states:StartExecution"],
            resources=[generate_chapter_sfn.state_machine_arn]
        ))

        generate_chapter_integration = apigw.AwsIntegration(
            service="states",
            action="StartExecution", # Explicitly use StartExecution
            options=apigw.IntegrationOptions(
                credentials_role=api_gw_sfn_role,
                passthrough_behavior=apigw.PassthroughBehavior.NEVER, # Important: process the template
                request_templates={
                    "application/json": (
                        f"""
                        #set($rawCourseId = $input.path('$.course_id'))
                        #set($rawChapterId = $input.path('$.chapter_id'))
                        #set($rawUserId = $context.authorizer.claims.sub)
                        #set($escapedCourseId = $util.escapeJavaScript($rawCourseId))
                        #set($escapedChapterId = $util.escapeJavaScript($rawChapterId))
                        #set($escapedUserId = $util.escapeJavaScript($rawUserId))
                        {{
                        "input": "{{\\"course_id\\": \\"$escapedCourseId\\", \\"chapter_id\\": \\"$escapedChapterId\\", \\"user_id\\": \\"$escapedUserId\\"}}",
                        "stateMachineArn": "{generate_chapter_sfn.state_machine_arn}"
                        }}
                        """
                    )
                },
                integration_responses=[
                    apigw.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": json.dumps({
                                "message": "Execution started successfully.",
                                # $input refers to the output of the StartExecution call
                                "executionArn": "$util.escapeJavaScript($input.json('$.executionArn'))",
                                "startDate": "$util.escapeJavaScript($input.json('$.startDate'))"
                            })
                        },
                        # Ensure headers are set for the response
                        response_parameters={
                            'method.response.header.Content-Type': "'application/json'"
                        }
                    )
                ]
            )
        )

        # Integrations for Lambda functions (assuming proxy integration)
        generate_lesson_plan_integration = apigw.LambdaIntegration(generate_course_plan_function)
        get_course_list_integration = apigw.LambdaIntegration(get_course_list_function)
        get_lesson_content_integration = apigw.LambdaIntegration(get_lesson_content_function)
        get_lesson_plan_integration = apigw.LambdaIntegration(get_lesson_plan_function)
        check_chapter_generation_status_integration = apigw.LambdaIntegration(check_chapter_generation_status_function)
        get_multiple_choice_questions_integration = apigw.LambdaIntegration(get_multiple_choice_questions_function) # Added
        get_flashcards_integration = apigw.LambdaIntegration(get_flashcards_function) # Added for flashcards
        get_image_data_integration = apigw.LambdaIntegration(get_image_data_function) # Added
        delete_course_integration = apigw.LambdaIntegration(delete_course_function) # Added

        # Define resources and methods based on the image

        # /generate-chapter
        generate_chapter_resource = api.root.add_resource("generate-chapter")
        generate_chapter_resource.add_method(
            "POST",
            generate_chapter_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
            method_responses=[apigw.MethodResponse(
                status_code="200",
                response_parameters={
                    'method.response.header.Content-Type': True
                }
            )] # Define expected method response
        )

        # /generate-lesson-plan
        generate_lesson_plan_resource = api.root.add_resource("generate-course-plan")
        generate_lesson_plan_resource.add_method(
            "POST", 
            generate_lesson_plan_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        # /get-course-list
        get_course_list_resource = api.root.add_resource("get-course-list")
        get_course_list_resource.add_method(
            "GET", 
            get_course_list_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        # /get-lesson-content
        get_lesson_content_resource = api.root.add_resource("get-lesson-content")
        get_lesson_content_resource.add_method(
            "GET", 
            get_lesson_content_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        # /get-lesson-plan
        get_lesson_plan_resource = api.root.add_resource("get-course-plan")
        get_lesson_plan_resource.add_method(
            "GET", 
            get_lesson_plan_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        # /check-chapter-generation-status
        check_chapter_status_resource = api.root.add_resource("check-chapter-generation-status")
        check_chapter_status_resource.add_method(
            "GET", 
            check_chapter_generation_status_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        # --- Authentication Endpoints ---
        # The /auth/login, /auth/callback, /auth/logout endpoints are removed
        # as they were tied to the Cognito Hosted UI flow (domain).

        auth_resource = api.root.add_resource("auth")

        # POST /auth/signup
        auth_signup_integration = apigw.LambdaIntegration(auth_signup_function)
        signup_resource = auth_resource.add_resource("signup")
        signup_resource.add_method("POST", auth_signup_integration) # No authorizer

        # POST /auth/signin
        auth_signin_integration = apigw.LambdaIntegration(auth_signin_function)
        signin_resource = auth_resource.add_resource("signin")
        signin_resource.add_method("POST", auth_signin_integration) # No authorizer

        # POST /auth/verify-code
        auth_verify_code_integration = apigw.LambdaIntegration(auth_verify_code_function)
        verify_code_resource = auth_resource.add_resource("verify-code")
        verify_code_resource.add_method("POST", auth_verify_code_integration) # No authorizer

        # POST /auth/resend-verification-code
        auth_resend_verification_code_integration = apigw.LambdaIntegration(auth_resend_verification_code_function)
        resend_code_resource = auth_resource.add_resource("resend-verification-code")
        resend_code_resource.add_method("POST", auth_resend_verification_code_integration) # No authorizer

        # POST /auth/refresh-token
        auth_refresh_token_integration = apigw.LambdaIntegration(auth_refresh_token_function)
        refresh_token_resource = auth_resource.add_resource("refresh-token")
        refresh_token_resource.add_method("POST", auth_refresh_token_integration) # No authorizer
        
        # GET /auth/userinfo (Protected by Cognito Authorizer)
        get_user_info_integration = apigw.LambdaIntegration(get_user_info_function)
        userinfo_resource = auth_resource.add_resource("userinfo")
        userinfo_resource.add_method(
            "GET",
            get_user_info_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        # GET /questions (Protected by Cognito Authorizer, expects query params)
        questions_resource = api.root.add_resource("questions")
        questions_resource.add_method(
            "GET",
            get_multiple_choice_questions_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,            
        )

        # GET /flashcards (Protected by Cognito Authorizer, expects query params)
        flashcards_resource = api.root.add_resource("flashcards")
        flashcards_resource.add_method(
            "GET",
            get_flashcards_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,            
        )

        # POST /get-image (No authorizer, as it's for public image retrieval)
        get_image_resource = api.root.add_resource("get-image")
        get_image_resource.add_method(
            "GET", # Use POST to send S3 URL in query string
            get_image_data_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,            
            method_responses=[apigw.MethodResponse(
                status_code="200",
                response_parameters={
                    'method.response.header.Content-Type': True,
                    'method.response.header.Access-Control-Allow-Origin': True,
                    'method.response.header.Content-Disposition': True
                }
            )]
        )

        # DELETE /courses/{course_id}
        delete_course_resource = api.root.add_resource("delete-course")        
        delete_course_resource.add_method(
            "DELETE",
            delete_course_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        self.api = api
