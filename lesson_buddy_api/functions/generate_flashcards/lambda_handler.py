import json
import os
from typing import Dict, Any, List
from urllib import request, parse, error as urllib_error, parse as urlparse
import time
import boto3
import datetime

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

def get_api_info(model):
    if model == 'gemini-2.5-flash':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.5-flash-preview-04-17'
    if model == 'gemini-2.5-pro':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.5-pro-preview-05-06'
    if model == 'claude-4-sonnet':
        url = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        return url, api_key, 'us.anthropic.claude-sonnet-4-20250514-v1:0'
    if model == 'claude-3.7-sonnet':
        url = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        return url, api_key, 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
    if model == 'claude-3.5-haiku':
        url = 'http://Bedroc-Proxy-xVtSm3tV6xYe-1727257641.us-east-1.elb.amazonaws.com/api/v1/chat/completions'
        api_key = os.environ['BEDROCK_API_KEY']
        return url, api_key, 'us.anthropic.claude-3-5-haiku-20241022-v1:0'
    if model == 'gemini-2.0-flash':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.0-flash-001'
    if model == 'gemini-2.0-flash-lite':
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        api_key = os.environ['API_KEY']
        return url, api_key, 'gemini-2.0-flash-lite-001'
    # Fallback
    return get_api_info('gemini-2.0-flash')

def call_model(system_prompt, prompt, messages=None, output_format=None, tools=None, model='gemini-2.5-flash'):
    url, api_key, model_identifier = get_api_info(model)

    data = {
        "model": model_identifier,
        "messages": [],
        "max_tokens": 8192
    }

    data['messages'].append({"role": "system", "content": system_prompt})

    if messages is not None:
        data['messages'].extend(messages)
    
    data['messages'].append({"role": "user", "content": prompt})
    
    if output_format:
        data['response_format'] = {
            "type": "json_schema",
            "json_schema": {
                "name": "output",
                "schema": output_format  
            }
        }

    if tools:
        data['tools'] = tools

    data_bytes = json.dumps(data).encode('utf-8')
    
    max_retries = 5
    base_delay = 1
    max_delay = 10
    
    for attempt in range(max_retries + 1):
        if attempt == max_retries and model != 'gemini-2.0-flash':
            print(f"Retry limit reached. Falling back to gemini-2.0-flash model for final attempt.")
            url, api_key, model_identifier = get_api_info('gemini-2.0-flash')
            data['model'] = model_identifier
            
        req = request.Request(url, data=data_bytes, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')
        
        try:
            with request.urlopen(req) as resp:
                if resp.status == 200:
                    content = resp.read()
                    output = json.loads(content)
                    print("LLM Raw Output:", output)
                    if output.get('choices') and output['choices'][0].get('message'):
                        return output['choices'][0]['message']
                    else:
                        print(f"Unexpected LLM response structure: {output}")
                        if output.get('content') and isinstance(output['content'], list) and output['content'][0].get('text'):
                             return {"role": "assistant", "content": output['content'][0]['text']}
                        return {"role": "assistant", "content": json.dumps(output)}
                else:
                    error_content = resp.read().decode('utf-8')
                    print(f"HTTP Error: {resp.status} - {resp.reason}. Response: {error_content}")
                    if 400 <= resp.status < 500 and resp.status != 429:
                        raise Exception(f"HTTP Client Error: {resp.status} - {error_content}")
                    raise urllib_error.HTTPError(url, resp.status, error_content, resp.headers, None)
                    
        except Exception as e:
            if attempt == max_retries:
                print(f"Error: Final attempt failed after {max_retries} retries: {e}")
                return None
            
            is_http_error = isinstance(e, urllib_error.HTTPError)
            is_url_error = isinstance(e, urllib_error.URLError)
                
            if (is_http_error and e.code in [500, 502, 503, 504, 429]) or is_url_error:
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * 0.1 * (0.5 - (0.5 * attempt / max_retries))
                sleep_time = delay + jitter
                
                print(f"Attempt {attempt + 1} failed. Retrying in {sleep_time:.2f} seconds... Error: {e}")
                time.sleep(sleep_time)
            else:
                print(f"Non-retryable error: {e}")
                return None
    return None

def generate_flashcards_from_content(lesson_content_markdown: str) -> List[Dict[str, Any]]:
    """
    Generates flashcards from lesson content using an LLM.
    """
    system_prompt = """
    You are an expert in creating educational flashcards. Based on the provided lesson content,
    generate exactly 10 flashcards. Each flashcard should have:
    - A clear, concise question that tests understanding of key concepts
    - A comprehensive answer that explains the concept thoroughly
    - Focus on important definitions, processes, relationships, and applications
    - Ensure questions are varied (definitions, applications, comparisons, etc.)
    - Questions should encourage active recall and deep understanding
    Output the flashcards in the specified JSON format.
    """
    user_prompt = f"Here is the lesson content:\n\n{lesson_content_markdown}\n\nPlease generate 10 flashcards based on this content."

    flashcard_schema = {
        "type": "object",
        "properties": {
            "flashcards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "The flashcard question that tests understanding."},
                        "answer": {"type": "string", "description": "The comprehensive answer that explains the concept."}
                    },
                    "required": ["question", "answer"]
                },
                "minItems": 10,
                "maxItems": 10,
                "description": "A list of exactly 10 flashcards."
            }
        },
        "required": ["flashcards"]
    }

    max_validation_retries = 3
    validation_attempt = 0
    previous_error_feedback = ""
    
    while validation_attempt < max_validation_retries:
        validation_attempt += 1
        current_prompt = user_prompt
        if previous_error_feedback:
            current_prompt = f"{previous_error_feedback}\n\n{user_prompt}"
        
        print(f"Generating flashcards attempt {validation_attempt}/{max_validation_retries}...")
        if previous_error_feedback:
            print(f"Feedback to LLM for this attempt: {previous_error_feedback}")

        model_output = call_model(
            system_prompt=system_prompt,
            prompt=current_prompt,
            output_format=flashcard_schema,
            model='gemini-2.5-flash'
        )
        
        previous_error_feedback = ""

        if model_output and 'content' in model_output and model_output['content']:
            try:
                flashcards_data_str = model_output['content']
                print(f"LLM content string for flashcards (Attempt {validation_attempt}): {flashcards_data_str}")
                flashcards_data = json.loads(flashcards_data_str)
                
                if "flashcards" in flashcards_data and isinstance(flashcards_data["flashcards"], list):
                    valid_flashcards = []
                    error_messages_for_llm = []
                    
                    for i, flashcard in enumerate(flashcards_data["flashcards"]):
                        if not isinstance(flashcard, dict):
                            msg = f"Flashcard item {i+1} is not a dictionary: {flashcard}"
                            print(f"Warning (Attempt {validation_attempt}): {msg}")
                            error_messages_for_llm.append(msg)
                            continue
                            
                        required_keys = ["question", "answer"]
                        missing_keys = [k for k in required_keys if k not in flashcard]
                        if missing_keys:
                            msg = f"Flashcard item {i+1} missing required keys: {', '.join(missing_keys)}."
                            print(f"Warning (Attempt {validation_attempt}): {msg}")
                            error_messages_for_llm.append(msg)
                            continue
                            
                        question = flashcard.get("question", "").strip()
                        answer = flashcard.get("answer", "").strip()
                        
                        if not question or not answer:
                            msg = f"Flashcard item {i+1} has empty question or answer."
                            print(f"Warning (Attempt {validation_attempt}): {msg}")
                            error_messages_for_llm.append(msg)
                            continue
                            
                        valid_flashcards.append(flashcard)
                    
                    if not error_messages_for_llm and len(valid_flashcards) == 10:
                        print(f"Successfully generated {len(valid_flashcards)} valid flashcards on attempt {validation_attempt}.")
                        return valid_flashcards
                    else:
                        if len(valid_flashcards) != 10:
                            error_messages_for_llm.append(f"Generated {len(valid_flashcards)} valid flashcards, but require exactly 10.")
                        
                        feedback_intro = f"This is attempt {validation_attempt + 1} of {max_validation_retries}. In the previous attempt (attempt {validation_attempt}), the following issues were found:"
                        previous_error_feedback = f"{feedback_intro}\n- " + "\n- ".join(error_messages_for_llm)
                        print(f"Warning (Attempt {validation_attempt}): Validation issues found. {len(valid_flashcards)} valid flashcards. Details: {previous_error_feedback}")
                
                else:
                    err_msg = f"'flashcards' key not found or not a list in LLM response JSON: {flashcards_data}"
                    print(f"Error (Attempt {validation_attempt}): {err_msg}")
                    previous_error_feedback = f"This is attempt {validation_attempt + 1} of {max_validation_retries}. In the previous attempt (attempt {validation_attempt}), the output was not structured correctly: {err_msg}"

            except json.JSONDecodeError as e:
                err_msg = f"Error decoding JSON from LLM: {e}. Raw content: {model_output.get('content', 'Content not available')}"
                print(f"Error (Attempt {validation_attempt}): {err_msg}")
                previous_error_feedback = f"This is attempt {validation_attempt + 1} of {max_validation_retries}. In the previous attempt (attempt {validation_attempt}), the output was not valid JSON. {err_msg}"
            except TypeError as e: 
                err_msg = f"Error processing LLM content (TypeError): {e}. LLM model_output: {model_output}"
                print(f"Error (Attempt {validation_attempt}): {err_msg}")
                previous_error_feedback = f"This is attempt {validation_attempt + 1} of {max_validation_retries}. In the previous attempt (attempt {validation_attempt}), there was a TypeError processing the output. {err_msg}"
        else: 
            err_msg = "LLM call failed or did not return content."
            print(f"Error (Attempt {validation_attempt}): {err_msg}")
            if model_output:
                print(f"LLM model_output: {model_output}")
            previous_error_feedback = f"This is attempt {validation_attempt + 1} of {max_validation_retries}. In the previous attempt (attempt {validation_attempt}), the model call failed or returned no content."
        
        if validation_attempt < max_validation_retries:
            print(f"Validation failed on attempt {validation_attempt}. Retrying...")
            time.sleep(1 + validation_attempt)
        else:
            print(f"Max validation retries ({max_validation_retries}) reached. Failed to generate sufficient valid flashcards.")
            return [] 

    return []

def _load_lesson_content_from_s3(s3_url: str) -> Dict[str, str]:
    """
    Loads lesson content from an S3 URL.
    """
    print(f"Loading lesson content from S3 URL: {s3_url}")
    parsed_url = urlparse.urlparse(s3_url)
    if parsed_url.scheme != 's3':
        raise ValueError(f"Invalid S3 URL scheme: {s3_url}")
    
    bucket_name = parsed_url.netloc
    object_key = parsed_url.path.lstrip('/')
    
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        content_string = response['Body'].read().decode('utf-8')
        lesson_content_dict = json.loads(content_string)
        if not isinstance(lesson_content_dict, dict):
            raise ValueError(f"Content from S3 ({s3_url}) is not a JSON dictionary.")
        print(f"Successfully loaded and parsed lesson content from {s3_url}")
        return lesson_content_dict
    except Exception as e:
        print(f"Error loading lesson content from S3 (s3://{bucket_name}/{object_key}): {e}")
        raise

def _save_flashcards_to_dynamodb(flashcards: List[Dict[str, Any]], course_id: str, chapter_id: str, lesson_id: str, user_id: str = None) -> str:
    """
    Saves flashcards to DynamoDB table.
    """
    flashcards_table_name = os.environ.get('FLASHCARDS_TABLE_NAME')
    if not flashcards_table_name:
        raise ValueError("FLASHCARDS_TABLE_NAME environment variable not set.")
    
    table = dynamodb.Table(flashcards_table_name)
    timestamp = datetime.datetime.utcnow().isoformat()
    
    # Clear existing flashcards for this lesson first
    lesson_flashcard_id = f"FLASHCARD#{course_id}#{chapter_id}#{lesson_id}"
    
    try:
        # Query existing items to delete them
        response = table.query(
            KeyConditionExpression="LessonFlashcardId = :lesson_id",
            ExpressionAttributeValues={":lesson_id": lesson_flashcard_id}
        )
        
        # Delete existing flashcards
        with table.batch_writer() as batch:
            for item in response.get('Items', []):
                batch.delete_item(Key={
                    'LessonFlashcardId': item['LessonFlashcardId'], 
                    'CardId': item['CardId']
                })
        
        print(f"Deleted {len(response.get('Items', []))} existing flashcards for lesson {lesson_id}")
        
        # Insert new flashcards
        with table.batch_writer() as batch:
            for i, flashcard in enumerate(flashcards):
                item = {
                    'LessonFlashcardId': lesson_flashcard_id,
                    'CardId': f"CARD#{i+1:02d}",
                    'CourseID': course_id,
                    'ChapterID': chapter_id,
                    'LessonID': lesson_id,
                    'Question': flashcard['question'],
                    'Answer': flashcard['answer'],
                    'CardNumber': i + 1,
                    'CreatedAt': timestamp
                }
                if user_id:
                    item['UserID'] = user_id
                batch.put_item(Item=item)
        
        print(f"Successfully saved {len(flashcards)} flashcards to DynamoDB")
        return lesson_flashcard_id
        
    except Exception as e:
        print(f"Error saving flashcards to DynamoDB: {e}")
        raise

def lambda_handler(event, context):
    """
    Lambda function to generate flashcards for a specific lesson.
    Expects input that includes course_id, chapter_id, lesson_id, and lesson_s3_url.
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        course_id = event.get('course_id')
        chapter_id = event.get('chapter_id')
        lesson_id = event.get('lesson_id')
        lesson_s3_url = event.get('lesson_s3_url')
        user_id = event.get('user_id')  # Optional

        if not all([course_id, chapter_id, lesson_id, lesson_s3_url]):
            missing_items = [
                k for k, v in {
                    'course_id': course_id, 
                    'chapter_id': chapter_id, 
                    'lesson_id': lesson_id,
                    'lesson_s3_url': lesson_s3_url
                }.items() if not v
            ]
            raise ValueError(f"Missing required items in input event: {', '.join(missing_items)}")

        # Load lesson content from S3
        lesson_content_dict = _load_lesson_content_from_s3(lesson_s3_url)
        
        # Combine dictionary values into a single markdown string
        lesson_markdown_string = "\n\n".join(lesson_content_dict.values())

        if not lesson_markdown_string.strip():
             raise ValueError(f"Lesson content from S3 URL {lesson_s3_url} is empty or invalid after processing.")

        # Generate flashcards
        flashcards = generate_flashcards_from_content(lesson_markdown_string)
        
        if not flashcards:
            print(f"Warning: No flashcards were generated for lesson {lesson_id} from {lesson_s3_url}.")
            raise ValueError(f"No flashcards were generated from the lesson content at {lesson_s3_url}.")

        # Save flashcards to DynamoDB
        flashcards_pk = _save_flashcards_to_dynamodb(flashcards, course_id, chapter_id, lesson_id, user_id)
        
        return {
            "course_id": course_id,
            "chapter_id": chapter_id,
            "lesson_id": lesson_id,
            "lesson_flashcard_id": flashcards_pk,
            "flashcards_count": len(flashcards)
        }

    except Exception as e:
        print(f"Error in generate_flashcards lambda_handler: {str(e)}")
        raise
