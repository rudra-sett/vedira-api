import json

def lambda_handler(event, context):
    """
    Lambda function to generate flashcards for a specific lesson.
    It takes course ID, chapter ID, and lesson ID as input.
    """
    try:
        # Extract IDs from the event body
        body = json.loads(event['body'])
        course_id = body.get('course_id')
        chapter_id = body.get('chapter_id')
        lesson_id = body.get('lesson_id')

        if not all([course_id, chapter_id, lesson_id]):
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing one or more required IDs: course_id, chapter_id, lesson_id'})
            }

        # TODO: Implement flashcard generation logic here
        # This would typically involve:
        # 1. Fetching lesson content using the provided IDs.
        # 2. Processing the content to extract key terms/concepts.
        # 3. Generating flashcards (e.g., question-answer pairs).
        # 4. Storing the generated flashcards in a database or S3.

        # Placeholder response for now
        response_message = (
            f"Flashcard generation initiated for "
            f"Course ID: {course_id}, Chapter ID: {chapter_id}, Lesson ID: {lesson_id}. "
            f"Flashcards will be generated soon."
        )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': response_message})
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid JSON in request body'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': str(e)})
        }
