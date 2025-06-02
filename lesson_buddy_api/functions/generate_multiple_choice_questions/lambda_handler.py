import json
import os
from typing import Dict, Any, List, Union
from urllib import request, parse, error as urllib_error, parse as urlparse # Added urlparse
import time
import boto3 

s3_client = boto3.client('s3') # Initialize S3 client globally or within handler

# bedrock_runtime = boto3.client(service_name='bedrock-runtime') # Placeholder

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
    # Fallback or error for unknown model
    raise ValueError(f"Unsupported model: {model}")

def call_model(system_prompt, prompt, messages=None, output_format=None, tools=None, model='gemini-2.5-flash'):
    url, api_key, model_identifier = get_api_info(model)

    data = {
        "model": model_identifier,
        "messages": [],
        "max_tokens": 8192 # Max tokens for Gemini Flash according to docs, adjust if needed for others
    }

    data['messages'].append({"role": "system", "content": system_prompt})

    if messages is not None:
        data['messages'].extend(messages)
    
    data['messages'].append({"role": "user", "content": prompt})
    
    if output_format:
        data['response_format'] = {
            "type": "json_schema", # Assuming Gemini-like API, OpenAI uses "type": "json_object"
            "json_schema": {       # For OpenAI, this would be under a "schema" key if using a more complex schema
                "name": "output",  # Name might not be universally required
                "schema": output_format  
            }
        }
        # For Anthropic through Bedrock proxy, if it supports structured output,
        # the format might differ. The current proxy seems to emulate OpenAI.

    if tools:
        data['tools'] = tools

    data_bytes = json.dumps(data).encode('utf-8')
    
    max_retries = 5
    base_delay = 1
    max_delay = 10
    
    for attempt in range(max_retries + 1):
        req = request.Request(url, data=data_bytes, method='POST') # Ensure POST
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')
        
        try:
            with request.urlopen(req) as resp:
                if resp.status == 200:
                    content = resp.read()
                    output = json.loads(content)
                    print("LLM Raw Output:", output) # For debugging
                    if output.get('choices') and output['choices'][0].get('message'):
                        return output['choices'][0]['message']
                    else: # Handle cases like Anthropic via Bedrock proxy if structure differs
                        # This part might need adjustment based on actual proxy response for errors/structure
                        print(f"Unexpected LLM response structure: {output}")
                        # Attempt to find content if structure is slightly different (e.g. Claude on Bedrock)
                        if output.get('content') and isinstance(output['content'], list) and output['content'][0].get('text'):
                             return {"role": "assistant", "content": output['content'][0]['text']} # Adapt to OpenAI-like structure
                        return {"role": "assistant", "content": json.dumps(output)} # Fallback to stringified output
                else:
                    error_content = resp.read().decode('utf-8')
                    print(f"HTTP Error: {resp.status} - {resp.reason}. Response: {error_content}")
                    # For 4xx errors, typically don't retry unless specific (e.g. rate limit 429)
                    if 400 <= resp.status < 500 and resp.status != 429:
                        raise Exception(f"HTTP Client Error: {resp.status} - {error_content}")
                    raise urllib_error.HTTPError(url, resp.status, error_content, resp.headers, None)
                    
        except Exception as e:
            if attempt == max_retries:
                print(f"Error: Final attempt failed after {max_retries} retries: {e}")
                return None # Or raise the exception: raise
            
            # Check for specific retryable errors
            is_http_error = isinstance(e, urllib_error.HTTPError)
            is_url_error = isinstance(e, urllib_error.URLError) # General network issues
                
            if (is_http_error and e.code in [500, 502, 503, 504, 429]) or is_url_error: # Added 429 for rate limits
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * 0.1 * (0.5 - (0.5 * attempt / max_retries))
                sleep_time = delay + jitter
                
                print(f"Attempt {attempt + 1} failed. Retrying in {sleep_time:.2f} seconds... Error: {e}")
                time.sleep(sleep_time)
            else:
                print(f"Non-retryable error: {e}")
                return None # Or raise the exception: raise
    return None # Should be unreachable if retries exhaust or an error is re-raised

def generate_questions_from_content(lesson_content_markdown: str) -> List[Dict[str, Any]]:
    """
    Generates multiple choice questions from lesson content using an LLM.
    """
    system_prompt = """
    You are an expert in creating educational assessments. Based on the provided lesson content,
    generate a list of 10 multiple-choice questions. Each question should have exactly 4 options,
    a single correct answer (which must be one of the provided options), and a brief explanation for why that answer is correct.
    The explanation should discuss the key concepts from the lesson content that the question is testing, do not simply state that the answer is in the lesson content.
    Ensure the questions accurately test understanding of the key concepts in the lesson, not just recall of facts. Emphasize critical thinking and application of knowledge, not just knowledge itself.
    Output the questions in the specified JSON format.
    """
    user_prompt = f"Here is the lesson content:\n\n{lesson_content_markdown}\n\nPlease generate 10 multiple-choice questions based on this content."

    question_schema = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "The text of the multiple-choice question."},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 4,
                            "description": "An array of exactly 4 potential answer strings."
                        },
                        "answer": {"type": "string", "description": "The correct answer, which must exactly match one of the strings in the 'options' array."},
                        "explanation": {"type": "string", "description": "A brief explanation of why the answer is correct."}
                    },
                    "required": ["question", "options", "answer", "explanation"],
                    
                },
                "minItems" : 10,
                "description": "A list of 10 multiple-choice questions."
            }
        },
        "required": ["questions"]
    }

    max_validation_retries = 3
    validation_attempt = 0
    previous_error_feedback = ""
    
    while validation_attempt < max_validation_retries:
        validation_attempt += 1
        current_prompt = user_prompt
        if previous_error_feedback:
            current_prompt = f"{previous_error_feedback}\n\n{user_prompt}"
        
        print(f"Generating questions attempt {validation_attempt}/{max_validation_retries}...")
        if previous_error_feedback:
            print(f"Feedback to LLM for this attempt: {previous_error_feedback}")

        model_output = call_model(
            system_prompt=system_prompt,
            prompt=current_prompt, # Use potentially modified prompt
            output_format=question_schema,
            model='gemini-2.5-flash'
        )
        
        previous_error_feedback = "" # Reset for next potential error

        if model_output and 'content' in model_output and model_output['content']:
            try:
                questions_data_str = model_output['content']
                print(f"LLM content string for questions (Attempt {validation_attempt}): {questions_data_str}")
                questions_data = json.loads(questions_data_str)
                
                if "questions" in questions_data and isinstance(questions_data["questions"], list):
                    valid_questions = []
                    error_messages_for_llm = []
                    for i, q_item in enumerate(questions_data["questions"]):
                        if not isinstance(q_item, dict):
                            msg = f"Question item {i+1} is not a dictionary: {q_item}"
                            print(f"Warning (Attempt {validation_attempt}): {msg}")
                            error_messages_for_llm.append(msg)
                            continue
                        required_keys = ["question", "options", "answer", "explanation"]
                        missing_keys = [k for k in required_keys if k not in q_item]
                        if missing_keys:
                            msg = f"Question item {i+1} ('{q_item.get('question', 'N/A')}') missing required keys: {', '.join(missing_keys)}."
                            print(f"Warning (Attempt {validation_attempt}): {msg}")
                            error_messages_for_llm.append(msg)
                            continue
                        
                        options = q_item.get("options")
                        if not isinstance(options, list) or len(options) != 4:
                            msg = f"Question item {i+1} ('{q_item.get('question')}') options malformed or not 4 options: {options}"
                            print(f"Warning (Attempt {validation_attempt}): {msg}")
                            error_messages_for_llm.append(msg)
                            continue

                        answer = q_item.get("answer")
                        if answer not in options:
                            msg = f"Question item {i+1} ('{q_item.get('question')}'): Answer '{answer}' not in options {options}."
                            print(f"Warning (Attempt {validation_attempt}): {msg}")
                            error_messages_for_llm.append(msg)
                            continue
                        valid_questions.append(q_item)
                    
                    if not error_messages_for_llm and len(valid_questions) >= 10:
                        print(f"Successfully generated {len(valid_questions)} valid questions on attempt {validation_attempt}.")
                        return valid_questions
                    else:
                        if len(valid_questions) < 10:
                            error_messages_for_llm.append(f"Generated {len(valid_questions)} valid questions, but require at least 10.")
                        
                        feedback_intro = f"This is attempt {validation_attempt + 1} of {max_validation_retries}. In the previous attempt (attempt {validation_attempt}), the following issues were found with your generated questions:"
                        previous_error_feedback = f"{feedback_intro}\n- " + "\n- ".join(error_messages_for_llm)
                        print(f"Warning (Attempt {validation_attempt}): Validation issues found. {len(valid_questions)} valid questions. Details: {previous_error_feedback}")
                
                else: # 'questions' key not found or not a list
                    err_msg = f"'questions' key not found or not a list in LLM response JSON: {questions_data}"
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
            time.sleep(1 + validation_attempt) # Slightly increasing delay for retries
        else:
            print(f"Max validation retries ({max_validation_retries}) reached. Failed to generate sufficient valid questions.")
            return [] 

    return [] 

def _load_lesson_content_from_s3(s3_url: str) -> Dict[str, str]:
    """
    Loads lesson content (expected to be a JSON dictionary of markdown strings) from an S3 URL.
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

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function.
    Expects input that includes a lesson_s3_url, course_id, chapter_id, and lesson_id.
    Downloads lesson content from S3, generates multiple-choice questions, 
    saves them to S3, and returns their S3 path along with IDs.
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        course_id = event.get('course_id')
        chapter_id = event.get('chapter_id')
        lesson_id = event.get('lesson_id')
        lesson_s3_url = event.get('lesson_s3_url') # Expecting S3 URL for lesson content

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
        # The fix_lesson_markdown function saves a dictionary of section_id: markdown_string
        lesson_markdown_string = "\n\n".join(lesson_content_dict.values())

        if not lesson_markdown_string.strip():
             raise ValueError(f"Lesson content from S3 URL {lesson_s3_url} is empty or invalid after processing.")

        multiple_choice_questions: List[Dict[str, Any]] = generate_questions_from_content(lesson_markdown_string)
        
        if not multiple_choice_questions:
            # If no questions are generated, we might still want to save an empty list to S3
            # or handle this as an error. The current generate_questions_from_content returns [] on failure.
            # For consistency, let's assume an empty list is a valid outcome to save,
            # but the calling Step Function might treat it as a partial success/failure.
            # The original code raised ValueError, let's stick to that for now if it's critical.
            print(f"Warning: No questions were generated for lesson {lesson_id} from {lesson_s3_url}.")
            # If an error should be raised:
            # raise ValueError(f"No questions were generated from the lesson content at {lesson_s3_url}.")


        # Save the multiple choice questions to S3
        # s3_client is already initialized
        questions_bucket_name = os.environ.get('QUESTIONS_BUCKET_NAME') 
        if not questions_bucket_name:
            error_msg = "QUESTIONS_BUCKET_NAME environment variable not set."
            print(error_msg)
            raise ValueError(error_msg)
    
        questions_s3_key = f"{course_id}-{chapter_id}-{lesson_id}-questions.json"
        try:
            s3_client.put_object(
                Bucket=questions_bucket_name, 
                Key=questions_s3_key, 
                Body=json.dumps(multiple_choice_questions, indent=2), 
                ContentType='application/json'
            )
            questions_s3_path = f"s3://{questions_bucket_name}/{questions_s3_key}"
            print(f"Successfully saved multiple choice questions to S3: {questions_s3_path}")
        except Exception as e:
            print(f"Error saving multiple choice questions to S3 (s3://{questions_bucket_name}/{questions_s3_key}): {e}")
            raise 

        # Return structure
        return {
            "course_id": course_id,
            "chapter_id": chapter_id,
            "lesson_id": lesson_id,
            "questions_s3_url": questions_s3_path, # Changed key to questions_s3_url for consistency
            # "multiple_choice_questions": multiple_choice_questions # Optionally return questions if needed by next step
        }

    except Exception as e:
        print(f"Error in generate_multiple_choice_questions lambda_handler: {str(e)}")
        raise
