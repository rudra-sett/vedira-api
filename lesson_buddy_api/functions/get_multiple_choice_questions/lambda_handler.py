import json
import os
import boto3
import logging
import base64

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")
# The bucket name will be retrieved from the Lambda environment variables
QUESTIONS_BUCKET_NAME = os.environ.get("QUESTIONS_BUCKET_NAME") 

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    if not QUESTIONS_BUCKET_NAME:
        logger.error("QUESTIONS_BUCKET_NAME environment variable not set.")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Server configuration error: Bucket name not set."
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
        }

    try:
        # Extract query string parameters
        query_params = event.get("queryStringParameters", {})
        if query_params is None: # API Gateway might pass None if no query params
            query_params = {}

        # Extract User ID from the Authorization header
        user_id = None
        try:
            auth_header = event.get('headers', {}).get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                logger.error("Missing or malformed Authorization header")
                return {
                    "statusCode": 401,
                    "body": json.dumps({"error": "Missing or malformed Authorization header"}),
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                }
            
            token = auth_header.split(' ')[1]
            payload_b64 = token.split('.')[1]
            payload_b64 += '=' * (-len(payload_b64) % 4)
            decoded_payload = base64.b64decode(payload_b64).decode('utf-8')
            payload_json = json.loads(decoded_payload)
            user_id = payload_json.get('sub')

            if not user_id:
                logger.error("User ID (sub) not found in token")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "User ID (sub) not found in token"}),
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                }
            logger.info(f"Extracted user_id: {user_id}") # Log the user_id
        except Exception as e:
            logger.error(f"Error decoding token or extracting sub: {str(e)}")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": f"Invalid token: {str(e)}"}),
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            }
            
        course_id = query_params.get("course_id")
        chapter_id = query_params.get("chapter_id")
        lesson_id = query_params.get("lesson_id")

        if not all([course_id, chapter_id, lesson_id]): # user_id is now also required implicitly by token
            logger.error("Missing one or more query string parameters: courseId, chapterId, lessonId")
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Missing required query string parameters: courseId, chapterId, lessonId"
                }),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
            }

        # Construct the S3 key for the multiple choice questions
        # Based on generate_multiple_choice_questions/lambda_handler.py
        s3_key = f"{course_id}-{chapter_id}-{lesson_id}-questions.json"
        logger.info(f"Attempting to retrieve object from S3: Bucket='{QUESTIONS_BUCKET_NAME}', Key='{s3_key}'")

        try:
            response = s3_client.get_object(Bucket=QUESTIONS_BUCKET_NAME, Key=s3_key)
            questions_content = response["Body"].read().decode("utf-8")
            questions_data = json.loads(questions_content)
            
            logger.info(f"Successfully retrieved and parsed questions for: {s3_key}")
            return {
                "statusCode": 200,
                "body": json.dumps(questions_data),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
            }
        except s3_client.exceptions.NoSuchKey:
            logger.warning(f"Multiple choice questions file not found at s3://{QUESTIONS_BUCKET_NAME}/{s3_key}")
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Multiple choice questions not found for the specified lesson."
                }),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
            }
        except Exception as e:
            logger.error(f"Error retrieving or parsing S3 object s3://{QUESTIONS_BUCKET_NAME}/{s3_key}: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": f"Failed to retrieve multiple choice questions: {str(e)}"
                }),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
            }

    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"An unexpected error occurred: {str(e)}"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
        }
