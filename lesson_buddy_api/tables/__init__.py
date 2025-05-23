from aws_cdk import (
    aws_dynamodb as dynamodb,
    RemovalPolicy
)
from constructs import Construct

class Tables(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.table = dynamodb.Table(
            self, "CoursePlanTable",
            partition_key=dynamodb.Attribute(
                name="CourseID", # From generate_course_plan
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="UserID",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY # Default, can be changed
        )

        # Add Global Secondary Index based on get_all_courses
        self.table.add_global_secondary_index(
            index_name="UserID-index", # From get_all_courses
            partition_key=dynamodb.Attribute(
                name="UserID", # From get_all_courses
                type=dynamodb.AttributeType.STRING
            )
            # You can specify read/write capacity if not using PAY_PER_REQUEST for the GSI
        )
