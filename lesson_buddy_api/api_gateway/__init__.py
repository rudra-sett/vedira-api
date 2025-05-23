from aws_cdk import (
    aws_apigateway as apigw,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_iam as iam # Added for potential Step Functions role if needed for sync
)
from constructs import Construct
import json

class LessonBuddyApiGateway(Construct):
    def __init__(self, scope: Construct, id: str,
                 generate_chapter_sfn: sfn.IStateMachine,
                 generate_course_plan_function: _lambda.IFunction,
                 get_course_list_function: _lambda.IFunction,
                 get_lesson_content_function: _lambda.IFunction,
                 get_lesson_plan_function: _lambda.IFunction,
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
                passthrough_behavior=apigw.PassthroughBehavior.NEVER,
                request_templates={
                    "application/json": json.dumps({
                        "input": "$util.escapeJavaScript($input.json('$'))",
                        "stateMachineArn": generate_chapter_sfn.state_machine_arn
                    })
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

        # Define resources and methods based on the image

        # /generate-chapter
        generate_chapter_resource = api.root.add_resource("generate-chapter")
        generate_chapter_resource.add_method(
            "POST",
            generate_chapter_integration,
            method_responses=[apigw.MethodResponse(
                status_code="200",
                response_parameters={
                    'method.response.header.Content-Type': True
                }
            )] # Define expected method response
        )

        # /generate-lesson-plan
        generate_lesson_plan_resource = api.root.add_resource("generate-course-plan")
        generate_lesson_plan_resource.add_method("POST", generate_lesson_plan_integration)

        # /get-course-list
        get_course_list_resource = api.root.add_resource("get-course-list")
        get_course_list_resource.add_method("GET", get_course_list_integration)

        # /get-lesson-content
        get_lesson_content_resource = api.root.add_resource("get-lesson-content")
        get_lesson_content_resource.add_method("GET", get_lesson_content_integration)

        # /get-lesson-plan
        get_lesson_plan_resource = api.root.add_resource("get-course-plan")
        get_lesson_plan_resource.add_method("GET", get_lesson_plan_integration)

        self.api = api
