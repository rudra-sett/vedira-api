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
        tables = Tables(self, "Tables")
        buckets = Buckets(self, "Buckets")

        # Add the FunctionStack and AuthenticationStack to the main stack
        authentication = Authentication(self, "Authentication")
        # Pass the table, bucket, and Cognito details to the FunctionStack
        functions = Functions(
            self, "Functions", 
            course_table=tables.table, 
            lesson_bucket=buckets.bucket,
            questions_bucket=buckets.questions_bucket, # Added questions_bucket
            course_images_bucket=buckets.course_images_bucket, # Added course_images_bucket
            flashcards_table=tables.flashcards_table, # Added flashcards_table
            user_pool_id=authentication.user_pool.user_pool_id,
            user_pool_client_id=authentication.user_pool_client.user_pool_client_id,
            user_pool_arn=authentication.user_pool.user_pool_arn
        )
        
        # Add the API Gateway Stack
        # Ensure FunctionStack exposes these attributes:
        # generate_course_plan_sfn, generate_lesson_content_lambda,
        # get_all_courses_lambda, get_lesson_content_lambda, get_course_plan_lambda
        api_gateway_stack = LessonBuddyApiGateway(
            self, "ApiGateway",
            generate_chapter_sfn=functions.course_generation_sfn,
            generate_course_plan_function=functions.generate_course_plan_function,
            get_course_list_function=functions.get_all_courses_function,
            get_lesson_content_function=functions.get_lesson_content_function,
            get_lesson_plan_function=functions.get_course_plan_function,
            check_chapter_generation_status_function=functions.check_chapter_generation_status_function,
            # Authentication related parameters
            cognito_authorizer=authentication.authorizer,
            user_pool_client=authentication.user_pool_client, 
            get_user_info_function=functions.get_user_info_function,
            # Server-side auth flow functions
            auth_signup_function=functions.auth_signup_function,
            auth_signin_function=functions.auth_signin_function,
            auth_verify_code_function=functions.auth_verify_code_function, # Added this line
            auth_resend_verification_code_function=functions.auth_resend_verification_code_function,
            auth_refresh_token_function=functions.auth_refresh_token_function,
            get_multiple_choice_questions_function=functions.get_multiple_choice_questions_function,
            get_flashcards_function=functions.get_flashcards_function, # Added flashcards function
            get_image_data_function=functions.get_image_data_function, # Added
            delete_course_function=functions.delete_course_function # Added
        )
