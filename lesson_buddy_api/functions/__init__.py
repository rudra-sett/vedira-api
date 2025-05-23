from aws_cdk import (
    # Duration,
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

    def __init__(self, scope: Construct, construct_id: str, course_table: dynamodb.ITable, lesson_bucket: s3.IBucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        load_dotenv() # Ensure .env is loaded for API_KEY

        # Add function to the stack from folder generate_course
        self.generate_course_plan_function = _lambda.Function(
            self, "GenerateCourseFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/generate_course_plan"),
            environment={
                "API_KEY": os.environ.get("API_KEY", "")
            }
        )
        course_table.grant_write_data(self.generate_course_plan_function)

        # Add function to the stack from folder get_lesson_content
        self.get_lesson_content_function = _lambda.Function(
            self, "GetLessonContentFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/get_lesson_content"),
        )
        lesson_bucket.grant_read(self.get_lesson_content_function)

        # Add function to the stack from folder get_all_courses
        self.get_all_courses_function = _lambda.Function(
            self, "GetAllCoursesFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/get_all_courses"),
        )
        course_table.grant_read_data(self.get_all_courses_function)
        
        # Add function to the stack from folder get_course_plan
        self.get_course_plan_function = _lambda.Function(
            self, "GetCoursePlanFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler", 
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/get_course_plan"),
        )
        course_table.grant_read_data(self.get_course_plan_function)

        # Add function to the stack from folder generate_lesson_content
        self.generate_lesson_content_function = _lambda.Function(
            self, "GenerateLessonContentFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler", 
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/generate_lesson_content"),
        )
        lesson_bucket.grant_write(self.generate_lesson_content_function)

        # Add function to the stack from folder mark_lesson_generated
        self.mark_lesson_generated_function = _lambda.Function(
            self, "MarkLessonGeneratedFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="lambda_handler.lambda_handler", 
            code=_lambda.Code.from_asset("lesson_buddy_api/functions/mark_lesson_generated"),
        )
        course_table.grant_write_data(self.mark_lesson_generated_function)

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
                "chapter_id": "{% $states.input.chapter_id %}"
            }
            },
            "Extract Chapter from Course Plan": {
            "Type": "Pass",
            "Next": "Generate Each Lesson in Chapter",
            "Output": {
                "lessons": "{% $single($parse($states.input.body).chapters, function($v) {$v.id = $chapter_id}).lessons %}"
            },
            "Assign": {
                "course_plan": "{% $parse($states.input.body) %}"
            }
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
                    "End": True
                }
                }
            },
            "Next": "Save Lesson States to S3",
            "Items": "{% $states.input.lessons %}"
            },
            "Save Lesson States to S3": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Output": "{% $states.result.Payload %}",
            "Arguments": {
                "FunctionName": self.mark_lesson_generated_function.function_arn,
                "Payload": {
                "updated_lessons": "{% $states.input %}",
                "course_plan": "{% $course_plan %}"
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
            self.mark_lesson_generated_function
        ]

        for lambda_func in lambda_functions_to_invoke:
            lambda_func.grant_invoke(self.course_generation_sfn.role)
