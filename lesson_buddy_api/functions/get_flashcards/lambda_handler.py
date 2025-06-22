import json
import os
import boto3
import logging
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    """
    Lambda function to retrieve flashcards for a specific lesson.
    Expects query string parameters: courseId, chapterId, lessonId
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Get table name from environment
        flashcards_table_name = os.environ.get('FLASHCARDS_TABLE_NAME')
        if not flashcards_table_name:
            logger.error("FLASHCARDS_TABLE_NAME environment variable not set")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Server configuration error"
                }),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
            }
        
        table = dynamodb.Table(flashcards_table_name)
        
        # Extract query string parameters
        query_params = event.get('queryStringParameters') or {}
        course_id = query_params.get('courseId')
        chapter_id = query_params.get('chapterId')
        lesson_id = query_params.get('lessonId')

        if not all([course_id, chapter_id, lesson_id]):
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

        # Construct the partition key for the flashcards
        lesson_flashcard_id = f"FLASHCARD#{course_id}#{chapter_id}#{lesson_id}"
        logger.info(f"Querying flashcards with LessonFlashcardId: {lesson_flashcard_id}")

        try:
            # Query DynamoDB for flashcards
            response = table.query(
                KeyConditionExpression="LessonFlashcardId = :lesson_id",
                ExpressionAttributeValues={":lesson_id": lesson_flashcard_id},
                ScanIndexForward=True  # Sort by CardId ascending (CARD#01, CARD#02, etc.)
            )
            
            flashcards_items = response.get('Items', [])
            
            if not flashcards_items:
                logger.warning(f"No flashcards found for LessonFlashcardId: {lesson_flashcard_id}")
                return {
                    "statusCode": 404,
                    "body": json.dumps({
                        "error": "Flashcards not found for the specified lesson."
                    }),
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                    },
                }
            
            # Transform DynamoDB items to flashcards format
            flashcards = []
            for item in flashcards_items:
                flashcard = {
                    "cardNumber": item.get('CardNumber'),
                    "question": item.get('Question'),
                    "answer": item.get('Answer'),
                    "createdAt": item.get('CreatedAt')
                }
                flashcards.append(flashcard)
            
            # Sort by card number to ensure proper order
            flashcards.sort(key=lambda x: x.get('cardNumber', 0))
            
            logger.info(f"Successfully retrieved {len(flashcards)} flashcards for lesson {lesson_id}")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "flashcards": flashcards,
                    "count": len(flashcards),
                    "courseId": course_id,
                    "chapterId": chapter_id,
                    "lessonId": lesson_id
                }),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
            }
            
        except ClientError as e:
            logger.error(f"DynamoDB error querying flashcards for LessonFlashcardId {lesson_flashcard_id}: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": f"Failed to retrieve flashcards: {str(e)}"
                }),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
            }
        
    except Exception as e:
        logger.error(f"Unexpected error in get_flashcards lambda_handler: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": f"Internal server error: {str(e)}"
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
        } 