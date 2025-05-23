import json
import boto3

def lambda_handler(event, context):
        
    to_update = event['updated_lessons']
    course_plan = event['course_plan']

    for updated_lesson in to_update:
        for c, chapter in enumerate(course_plan["chapters"]):
            if chapter['id'] == updated_lesson['chapter_id']:                      
                for l, lesson in enumerate(chapter['lessons']):
                    if lesson['id'] == updated_lesson['lesson_id']:                    
                        course_plan['chapters'][c]['lessons'][l]['generated'] = True

    # save to dynamodb
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('LB-CourseTable') # type: ignore
    table.put_item(Item=course_plan)

    return {
        'statusCode': 200,
        'body': "Updated All Lessons"
    }
