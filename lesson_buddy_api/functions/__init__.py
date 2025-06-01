from aws_cdk import (
    Duration,
    # Stack, # Will be changed to Construct
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_iam as iam,
    aws_dynamodb as dynamodb, # Added for type hinting
    aws_s3 as s3, # Added for type hinting
)
from constructs import Construct # Will use Construct as the base class
from dotenv import load_dotenv
import os
import json

class Functions(Construct): # Changed from Stack to Construct

    def __init__(self, scope: Construct, construct_id: str, 
                 course_table: dynamodb.ITable, 
                 lesson_bucket: s3.IBucket,
                 questions_bucket: s3.IBucket, # Added questions_bucket
                 user_pool_id: str, # Added
                 user_pool_client_id: str, # Added
                 user_pool_arn: str, # Added for IAM permissions
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        load_dotenv() # Ensure .env is loaded for API_KEY

        # Add function to the stack from folder generate_course
        self.generate_course_plan_function = _lambda.Function(
            self, "GenerateCourseFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/generate_course_plan"),
            timeout=Duration.minutes(15),
            environment={
                "API_KEY": os.environ.get("API_KEY", ""),
                "BEDROCK_API_KEY": os.environ.get("BEDROCK_API_KEY", ""),
                "COURSE_TABLE_NAME": course_table.table_name
            }
        )
        course_table.grant_write_data(self.generate_course_plan_function)

        # Add function to the stack from folder get_lesson_content
        self.get_lesson_content_function = _lambda.Function(
            self, "GetLessonContentFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/get_lesson_content"),
            timeout=Duration.minutes(15),
            environment={
                "LESSON_BUCKET_NAME": lesson_bucket.bucket_name
            }
        )
        lesson_bucket.grant_read(self.get_lesson_content_function)

        # Add function to the stack from folder get_all_courses
        self.get_all_courses_function = _lambda.Function(
            self, "GetAllCoursesFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/get_all_courses"),
            timeout=Duration.minutes(15),
            environment={
                "COURSE_TABLE_NAME": course_table.table_name
            }
        )
        course_table.grant_read_data(self.get_all_courses_function)
        
        # Add function to the stack from folder get_course_plan
        self.get_course_plan_function = _lambda.Function(
            self, "GetCoursePlanFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler", 
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/get_course_plan"),
            timeout=Duration.minutes(15),
            environment={
                "COURSE_TABLE_NAME": course_table.table_name
            }
        )
        course_table.grant_read_data(self.get_course_plan_function)

        # Add function to the stack from folder generate_lesson_content
        self.generate_lesson_content_function = _lambda.Function(
            self, "GenerateLessonContentFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler", 
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/generate_lesson_content"),
            timeout=Duration.minutes(15),
            environment={
                "API_KEY": os.environ.get("API_KEY", ""),
                "BEDROCK_API_KEY": os.environ.get("BEDROCK_API_KEY", ""),
                "LESSON_BUCKET_NAME": lesson_bucket.bucket_name
            }
        )
        lesson_bucket.grant_write(self.generate_lesson_content_function)

        # Add function to the stack from folder fix_lesson_markdown
        self.fix_lesson_markdown_function = _lambda.Function(
            self, "FixLessonMarkdownFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/fix_lesson_markdown"),
            timeout=Duration.minutes(5), # Markdown fixing should be relatively quick
            environment={
                "API_KEY": os.environ.get("API_KEY", ""),
                "BEDROCK_API_KEY": os.environ.get("BEDROCK_API_KEY", ""),
                "LESSON_BUCKET_NAME": lesson_bucket.bucket_name
            }
        )
        lesson_bucket.grant_write(self.fix_lesson_markdown_function) # It needs to save the fixed content

        # Add function to the stack from folder generate_multiple_choice_questions
        self.generate_multiple_choice_questions_function = _lambda.Function(
            self, "GenerateMultipleChoiceQuestionsFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/generate_multiple_choice_questions"),
            timeout=Duration.minutes(5), 
            environment={
                "API_KEY": os.environ.get("API_KEY", ""), 
                "BEDROCK_API_KEY": os.environ.get("BEDROCK_API_KEY", ""),
                "QUESTIONS_BUCKET_NAME": questions_bucket.bucket_name # Added
            }
        )
        questions_bucket.grant_write(self.generate_multiple_choice_questions_function) # Added permissions

        # Add function to the stack from folder get_multiple_choice_questions
        self.get_multiple_choice_questions_function = _lambda.Function(
            self, "GetMultipleChoiceQuestionsFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/get_multiple_choice_questions"),
            timeout=Duration.minutes(1),
            environment={
                "QUESTIONS_BUCKET_NAME": questions_bucket.bucket_name
            }
        )
        questions_bucket.grant_read(self.get_multiple_choice_questions_function)

        # Add function to the stack from folder update_chapter_status (renamed from mark_lesson_generated)
        self.update_chapter_status_function = _lambda.Function(
            self, "UpdateChapterStatusFunction", # Renamed construct ID
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler", 
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/update_chapter_status"), # Updated code path
            timeout=Duration.minutes(15),
            environment={
                "COURSE_TABLE_NAME": course_table.table_name
            }
        )
        course_table.grant_write_data(self.update_chapter_status_function) # Grant to new function name

        # Add function to the stack from folder check_chapter_generation_status
        self.check_chapter_generation_status_function = _lambda.Function(
            self, "CheckChapterGenerationStatusFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.handler",  # Corrected handler name
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/check_chapter_generation_status"),
            timeout=Duration.minutes(1), # Short timeout as it's a status check
            environment={
                "COURSE_TABLE_NAME": course_table.table_name # Added for DynamoDB access
                # No specific environment variables needed for this function yet
            }
        )
        course_table.grant_read_data(self.check_chapter_generation_status_function) # Added DynamoDB read permission
        # Grant permission to describe Step Function executions
        self.check_chapter_generation_status_function.add_to_role_policy(iam.PolicyStatement(
            actions=["states:DescribeExecution"],
            resources=["*"] # Or be more specific if you have the ARN of the state machine
        ))

        # Add function for retrieving user info (protected by Cognito)
        self.get_user_info_function = _lambda.Function(
            self, "GetUserInfoFunction",
            runtime=_lambda.Runtime.PYTHON_3_13, # Match other functions
            handler="lambda_handler.handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/get_user_info"),
            timeout=Duration.seconds(30), # Typically short
            environment={
                # No specific environment variables needed for this function yet
            }
        )
        # No specific table/bucket permissions needed for this simple example


        # --- Server-side Authentication Lambda Functions ---

        self.auth_signup_function = _lambda.Function(
            self, "AuthSignupFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/auth_signup"),
            timeout=Duration.seconds(30),
            environment={
                "USER_POOL_ID": user_pool_id,
                "CLIENT_ID": user_pool_client_id
            }
        )
        # Grant permissions to interact with Cognito User Pool
        self.auth_signup_function.add_to_role_policy(iam.PolicyStatement(
            actions=["cognito-idp:SignUp"],
            resources=[user_pool_arn] # Restrict to the specific user pool
        ))

        self.auth_signin_function = _lambda.Function(
            self, "AuthSigninFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/auth_signin"),
            timeout=Duration.seconds(30),
            environment={
                "USER_POOL_ID": user_pool_id,
                "CLIENT_ID": user_pool_client_id
            }
        )
        self.auth_signin_function.add_to_role_policy(iam.PolicyStatement(
            actions=["cognito-idp:InitiateAuth", "cognito-idp:RespondToAuthChallenge"], # RespondToAuthChallenge might be needed
            resources=[user_pool_arn] # Restrict to the specific user pool
        ))
        # If client-specific secrets are used with USER_PASSWORD_AUTH (not typical for public clients but possible for confidential):
        # self.auth_signin_function.add_to_role_policy(iam.PolicyStatement(
        #     actions=["cognito-idp:AdminInitiateAuth"], # If using Admin flow
        #     resources=[user_pool_arn]
        # ))

        self.auth_verify_code_function = _lambda.Function(
            self, "AuthVerifyCodeFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler", # Assuming handler is lambda_handler.lambda_handler
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/auth_verify_code"),
            timeout=Duration.seconds(30),
            environment={
                "USER_POOL_ID": user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client_id, # Changed from CLIENT_ID to USER_POOL_CLIENT_ID for consistency
                "USERS_TABLE_NAME": course_table.table_name # Assuming you might want to update a user status table
            }
        )
        # Grant permissions to confirm sign-up in Cognito
        self.auth_verify_code_function.add_to_role_policy(iam.PolicyStatement(
            actions=["cognito-idp:ConfirmSignUp"],
            resources=[user_pool_arn] # Restrict to the specific user pool
        ))
        # If you update a DynamoDB table (e.g., users_table) after verification:
        # course_table.grant_write_data(self.auth_verify_code_function) # Or a specific users_table if different

        self.auth_resend_verification_code_function = _lambda.Function(
            self, "AuthResendVerificationCodeFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/auth_resend_verification_code"),
            timeout=Duration.seconds(30),
            environment={
                "USER_POOL_ID": user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client_id,
            }
        )
        # Grant permissions to resend confirmation code and get user details in Cognito
        self.auth_resend_verification_code_function.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "cognito-idp:ResendConfirmationCode",
                "cognito-idp:AdminGetUser" # Needed to check if user is already confirmed
            ],
            resources=[user_pool_arn] # Restrict to the specific user pool
        ))

        self.auth_refresh_token_function = _lambda.Function(
            self, "AuthRefreshTokenFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.handler", # Assuming handler is lambda_handler.handler
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/auth_refresh_token"),
            timeout=Duration.seconds(30),
            environment={
                "USER_POOL_ID": user_pool_id,
                "CLIENT_ID": user_pool_client_id
            }
        )
        self.auth_refresh_token_function.add_to_role_policy(iam.PolicyStatement(
            actions=["cognito-idp:InitiateAuth"], # REFRESH_TOKEN_AUTH uses InitiateAuth
            resources=[user_pool_arn]
        ))

        step_function_definition = {
            "Comment": "A description of my state machine",
            "StartAt": "Get Course Plan",
            "States": {
                "Get Course Plan": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Output": "{% $states.result.Payload %}",
                "Arguments": {
                    "FunctionName": self.get_course_plan_function.function_arn,
                    "Payload": {
                    "queryStringParameters": {
                        "course_id": "{% $states.input.course_id %}",
                        "user_id": "{% $states.input.user_id %}"
                    }
                    }
                },
                "Retry": [
                    {
                    "ErrorEquals": [
                        "Lambda.ServiceException",
                        "Lambda.AWSLambdaException",
                        "Lambda.SdkClientException",
                        "Lambda.TooManyRequestsException"
                    ],
                    "IntervalSeconds": 1,
                    "MaxAttempts": 3,
                    "BackoffRate": 2,
                    "JitterStrategy": "FULL"
                    }
                ],
                "Next": "Extract Chapter from Course Plan",
                "Assign": {
                    "chapter_id": "{% $states.input.chapter_id %}",
                    "user_id": "{% $states.input.user_id %}",
                    "course_id": "{% $states.input.course_id %}"
                }
                },
                "Extract Chapter from Course Plan": {
                "Type": "Pass",
                "Next": "Mark Chapter as Generating",
                "Output": {
                    "lessons": "{% $single($parse($states.input.body).chapters, function($v) {$v.id = $chapter_id}).lessons %}"
                },
                "Assign": {
                    "course_plan": "{% $parse($states.input.body) %}"
                }
                },
                "Mark Chapter as Generating": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Output": "{% $states.input %}",
                "Arguments": {
                    "FunctionName": self.update_chapter_status_function.function_arn,
                    "Payload": {
                    "course_id": "{% $course_id %}",
                    "user_id": "{% $user_id %}",
                    "chapter_id": "{% $chapter_id %}",
                    "status_type": "lessons",
                    "new_status": "GENERATING"
                    }
                },
                "Retry": [
                    {
                    "ErrorEquals": [
                        "Lambda.ServiceException",
                        "Lambda.AWSLambdaException",
                        "Lambda.SdkClientException",
                        "Lambda.TooManyRequestsException"
                    ],
                    "IntervalSeconds": 1,
                    "MaxAttempts": 3,
                    "BackoffRate": 2,
                    "JitterStrategy": "FULL"
                    }
                ],
                "Next": "Generate Each Lesson in Chapter"
                },
                "Generate Each Lesson in Chapter": {
                "Type": "Map",
                "ItemProcessor": {
                    "ProcessorConfig": {
                    "Mode": "INLINE"
                    },
                    "StartAt": "Generate Lesson Content",
                    "States": {
                    "Generate Lesson Content": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Output": "{% $states.result.Payload %}",
                        "Arguments": {
                        "FunctionName": self.generate_lesson_content_function.function_arn,
                        "Payload": {
                            "body": {
                            "lesson_id": "{% $states.input.id %}",
                            "chapter_id": "{% $chapter_id %}",
                            "course_plan": "{% $course_plan %}"
                            }
                        }
                        },
                        "Retry": [
                        {
                            "ErrorEquals": [
                            "Lambda.ServiceException",
                            "Lambda.AWSLambdaException",
                            "Lambda.SdkClientException",
                            "Lambda.TooManyRequestsException"
                            ],
                            "IntervalSeconds": 1,
                            "MaxAttempts": 3,
                            "BackoffRate": 2,
                            "JitterStrategy": "FULL"
                        }
                        ],
                        "Next": "Fix Lesson Markdown"
                    },
                    "Fix Lesson Markdown": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Output": "{% $states.result.Payload %}",
                        "Arguments": {
                        "FunctionName": self.fix_lesson_markdown_function.function_arn,
                        "Payload": "{% $states.input %}"
                        },
                        "Retry": [
                        {
                            "ErrorEquals": [
                            "Lambda.ServiceException",
                            "Lambda.AWSLambdaException",
                            "Lambda.SdkClientException",
                            "Lambda.TooManyRequestsException"
                            ],
                            "IntervalSeconds": 1,
                            "MaxAttempts": 3,
                            "BackoffRate": 2,
                            "JitterStrategy": "FULL"
                        }
                        ],
                        "End": True
                    }
                    }
                },
                "Next": "Parallel",
                "Items": "{% $states.input.lessons %}"
                },
                "Parallel": {
                "Type": "Parallel",
                "Branches": [
                    {
                    "StartAt": "Save Chapter State to DynamoDB",
                    "States": {
                        "Save Chapter State to DynamoDB": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Output": "{% $states.result.Payload %}",
                        "Arguments": {
                            "FunctionName": self.update_chapter_status_function.function_arn,
                            "Payload": {
                            "course_id": "{% $course_id %}",
                            "user_id": "{% $user_id %}",
                            "chapter_id": "{% $chapter_id %}",
                            "status_type": "lessons",
                            "new_status": "COMPLETED"
                            }
                        },
                        "Retry": [
                            {
                            "ErrorEquals": [
                                "Lambda.ServiceException",
                                "Lambda.AWSLambdaException",
                                "Lambda.SdkClientException",
                                "Lambda.TooManyRequestsException"
                            ],
                            "IntervalSeconds": 1,
                            "MaxAttempts": 3,
                            "BackoffRate": 2,
                            "JitterStrategy": "FULL"
                            }
                        ],
                        "End": True
                        }
                    }
                    },
                    {
                    "StartAt": "Mark MCQs as Generating",
                    "States": {
                        "Mark MCQs as Generating": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Output": "{% $states.input %}",
                        "Arguments": {
                            "FunctionName": self.update_chapter_status_function.function_arn,
                            "Payload": {
                            "course_id": "{% $course_id %}",
                            "user_id": "{% $user_id %}",
                            "chapter_id": "{% $chapter_id %}",
                            "status_type": "mcqs",
                            "new_status": "GENERATING"
                            }
                        },
                        "Retry": [
                            {
                            "ErrorEquals": [
                                "Lambda.ServiceException",
                                "Lambda.AWSLambdaException",
                                "Lambda.SdkClientException",
                                "Lambda.TooManyRequestsException"
                            ],
                            "IntervalSeconds": 1,
                            "MaxAttempts": 3,
                            "BackoffRate": 2,
                            "JitterStrategy": "FULL"
                            }
                        ],
                        "Next": "Generate Questions for Each Lesson"
                        },
                        "Generate Questions for Each Lesson": {
                        "Type": "Map",
                        "ItemProcessor": {
                            "ProcessorConfig": {
                            "Mode": "INLINE"
                            },
                            "StartAt": "Generate Questions",
                            "States": {
                            "Generate Questions": {
                                "Type": "Task",
                                "Resource": "arn:aws:states:::lambda:invoke",
                                "Output": "{% $states.result.Payload %}",
                                "Arguments": {
                                "FunctionName": self.generate_multiple_choice_questions_function.function_arn,
                                "Payload": "{% $states.input %}"
                                },
                                "Retry": [
                                {
                                    "ErrorEquals": [
                                    "Lambda.ServiceException",
                                    "Lambda.AWSLambdaException",
                                    "Lambda.SdkClientException",
                                    "Lambda.TooManyRequestsException"
                                    ],
                                    "IntervalSeconds": 1,
                                    "MaxAttempts": 3,
                                    "BackoffRate": 2,
                                    "JitterStrategy": "FULL"
                                }
                                ],
                                "End": True
                            }
                            }
                        },
                        "Next": "Save MCQ State to DynamoDB"
                        },
                        "Save MCQ State to DynamoDB": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Output": "{% $states.result.Payload %}",
                        "Arguments": {
                            "FunctionName": self.update_chapter_status_function.function_arn,
                            "Payload": {
                            "course_id": "{% $course_id %}",
                            "user_id": "{% $user_id %}",
                            "chapter_id": "{% $chapter_id %}",
                            "status_type": "mcqs",
                            "new_status": "COMPLETED"
                            }
                        },
                        "Retry": [
                            {
                            "ErrorEquals": [
                                "Lambda.ServiceException",
                                "Lambda.AWSLambdaException",
                                "Lambda.SdkClientException",
                                "Lambda.TooManyRequestsException"
                            ],
                            "IntervalSeconds": 1,
                            "MaxAttempts": 3,
                            "BackoffRate": 2,
                            "JitterStrategy": "FULL"
                            }
                        ],
                        "End": True
                        }
                    }
                    }
                ],
                "End": True
                }
            },
            "QueryLanguage": "JSONata"
            }
        
        step_function_definition_str = json.dumps(step_function_definition)

        self.course_generation_sfn = sfn.StateMachine(
            self, "ChapterGenerationStateMachine",
            definition_body=sfn.DefinitionBody.from_string(step_function_definition_str),
            state_machine_name="CourseGenerationStateMachine", # Added a more descriptive name
            state_machine_type=sfn.StateMachineType.STANDARD
        )
        
        lambda_functions_to_invoke = [
            self.get_course_plan_function,
            self.generate_lesson_content_function,
            self.fix_lesson_markdown_function,
            self.update_chapter_status_function, # Renamed from mark_lesson_generated_function
            self.generate_multiple_choice_questions_function # Added new function
        ]

        for lambda_func in lambda_functions_to_invoke:
            lambda_func.grant_invoke(self.course_generation_sfn.role)
