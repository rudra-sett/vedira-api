import json
import os
import boto3

def lambda_handler(event, context):
    """
    Handles the deletion of a course.
    """
    print(f"Received event: {event}")

    try:
        course_id = event['queryStringParameters']['course_id']
    except (KeyError, TypeError):
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Missing course_id in queryStringParameters'})
        }

    user_id = None
    # Attempt to get user_id from event context (API Gateway with Lambda Authorizer)
    try:
        user_id = event['requestContext']['authorizer']['claims']['sub']
        if not user_id:
            print("User ID (sub) is present but empty in authorizer claims.")
    except KeyError:
        print("User ID not found in event.requestContext.authorizer.claims.sub. Trying queryStringParameters.")
    except Exception as e:
        print(f"Unexpected error extracting user_id from event context: {str(e)}")

    # If user_id not found in event context, try to get it from queryStringParameters.
    if not user_id:
        try:
            data = event.get("queryStringParameters", {})
            user_id = data.get('user_id')
            if user_id:
                print("User ID obtained from queryStringParameters.")
            else:
                print("User ID also not found in queryStringParameters.")
        except Exception as e:
            print(f"Error getting user_id from queryStringParameters: {str(e)}")

    if not user_id:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'User ID could not be determined from token or event payload.'})
        }

    dynamodb = boto3.resource('dynamodb')
    courses_table_name = os.environ.get('COURSES_TABLE_NAME')
    if not courses_table_name:
        print("COURSES_TABLE_NAME environment variable not set.")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Internal server error: Courses table name not configured.'})
        }

    courses_table = dynamodb.Table(courses_table_name)

    try:
        response = courses_table.delete_item(
            Key={
                'CourseID': course_id,
                'UserID': user_id
            }
        )
        print(f"DynamoDB delete_item response: {response}")

        if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': f'Course {course_id} deleted successfully.'})
            }
        else:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Failed to delete course.'})
            }

    except Exception as e:
        print(f"Error deleting course: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': f'Error deleting course: {str(e)}'})
        }
