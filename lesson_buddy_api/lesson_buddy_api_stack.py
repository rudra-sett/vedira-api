from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
)
from constructs import Construct
from .functions import FunctionStack
from .authentication import AuthenticationStack
from .tables import Tables # Added import
from .buckets import Buckets # Added import

class LessonBuddyApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Instantiate Tables and Buckets
        tables = Tables(self, "LessonBuddyTables")
        buckets = Buckets(self, "LessonBuddyBuckets")

        # Add the FunctionStack and AuthenticationStack to the main stack
        # Pass the table and bucket to the FunctionStack
        function_stack = FunctionStack(self, "FunctionStack", course_table=tables.table, lesson_bucket=buckets.bucket)
        authentication_stack = AuthenticationStack(self, "AuthenticationStack")
