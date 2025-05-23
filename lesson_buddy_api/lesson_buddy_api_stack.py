from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
)
from constructs import Construct
from .functions import Functions
from .authentication import Authentication
from .tables import Tables # Added import
from .buckets import Buckets # Added import
from .api_gateway import LessonBuddyApiGateway # Added import

class LessonBuddyApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Instantiate Tables and Buckets
        tables = Tables(self, "TableStack")
        buckets = Buckets(self, "BucketStack")

        # Add the FunctionStack and AuthenticationStack to the main stack
        # Pass the table and bucket to the FunctionStack
        functions = Functions(self, "Functions", course_table=tables.table, lesson_bucket=buckets.bucket)
        authentication = Authentication(self, "Authentication")

        # Add the API Gateway Stack
        # Ensure FunctionStack exposes these attributes:
        # generate_course_plan_sfn, generate_lesson_content_lambda,
        # get_all_courses_lambda, get_lesson_content_lambda, get_course_plan_lambda
        api_gateway_stack = LessonBuddyApiGateway(
            self, "ApiGatewayStack",
            generate_chapter_sfn=functions.course_generation_sfn,
            generate_lesson_plan_function=functions.generate_lesson_content_function,
            get_course_list_function=functions.get_all_courses_function,
            get_lesson_content_function=functions.get_lesson_content_function,
            get_lesson_plan_function=functions.get_course_plan_function
        )
