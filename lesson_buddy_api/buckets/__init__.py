from aws_cdk import (
    aws_s3 as s3,
    RemovalPolicy
)
from constructs import Construct

class Buckets(Construct):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.bucket = s3.Bucket(
            self, "LessonContentS3Bucket",
            bucket_name="lesson-content-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
