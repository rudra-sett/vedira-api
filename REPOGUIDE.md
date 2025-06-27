# 📚 VEDIRA API - Repository Guide

## 🚀 **AWS Lambda-Powered Serverless Architecture**

**VEDIRA** is a **100% serverless educational platform** built entirely on **AWS Lambda functions** as the core compute layer. This Lambda-first architecture provides:

- **17 specialized Lambda functions** handling all business logic
- **Event-driven processing** for scalable content generation
- **Zero server management** with automatic scaling
- **Pay-per-execution** cost optimization
- **Seamless integration** with AWS services ecosystem

---

## 🏗️ **Project Overview**

VEDIRA API is a serverless educational platform built on AWS that generates AI-powered course content, including lessons, multiple-choice questions, and flashcards. The system uses **AWS Lambda as the primary compute service** with AWS CDK for infrastructure as code, leveraging multiple AWS services for a complete learning management solution.

### **Why AWS Lambda?**
- **Core Requirement**: All application logic runs on Lambda functions
- **Microservices Architecture**: Each function serves a single purpose
- **Event-Driven**: Functions trigger based on API calls and Step Functions workflows
- **Auto-Scaling**: Handles concurrent requests without manual scaling
- **Cost-Effective**: Pay only for actual execution time

---

## 📁 **Repository Structure**

```
lesson-buddy-api/
├── 📂 lesson_buddy_api/           # Main application package
│   ├── 📂 api_gateway/            # API Gateway configuration
│   ├── 📂 authentication/         # Cognito authentication setup
│   ├── 📂 buckets/               # S3 bucket definitions
│   ├── 📂 functions/             # Lambda functions (core business logic)
│   │   ├── 📂 auth_*             # Authentication functions
│   │   ├── 📂 generate_*         # Content generation functions
│   │   ├── 📂 get_*              # Data retrieval functions
│   │   └── 📂 update_*           # Data update functions
│   ├── 📂 tables/                # DynamoDB table definitions
│   └── 📄 lesson_buddy_api_stack.py  # Main CDK stack
├── 📂 tests/                     # Test files
├── 📄 app.py                     # CDK app entry point
├── 📄 cdk.json                   # CDK configuration
├── 📄 requirements.txt           # Python dependencies
└── 📄 requirements-dev.txt       # Development dependencies
```

---

## ⚡ **AWS Lambda Functions - The Heart of VEDIRA**

### **🔐 Authentication Functions (5 Lambda Functions)**
| Function | Purpose | Trigger | Runtime |
|----------|---------|---------|---------|
| `auth_signup` | User registration with Cognito | API Gateway POST /auth/signup | Python 3.13 |
| `auth_signin` | User login authentication | API Gateway POST /auth/signin | Python 3.13 |
| `auth_verify_code` | Email verification for new users | API Gateway POST /auth/verify-code | Python 3.13 |
| `auth_resend_verification_code` | Resend verification email | API Gateway POST /auth/resend-verification-code | Python 3.13 |
| `auth_refresh_token` | Refresh JWT access tokens | API Gateway POST /auth/refresh-token | Python 3.13 |

### **Course Management Functions (4 Lambda Functions)**
| Function | Purpose | Trigger | Runtime |
|----------|---------|---------|---------|
| `generate_course_plan` | Create AI-generated course structure | API Gateway POST /generate-course-plan | Python 3.13 |
| `get_all_courses` | Retrieve user's course list | API Gateway GET /get-course-list | Python 3.13 |
| `get_course_plan` | Get specific course details | API Gateway GET /get-course-plan | Python 3.13 |
| `delete_course` | Remove course and related data | API Gateway DELETE /delete-course | Python 3.13 |

### **Content Generation Functions (4 Lambda Functions)**
| Function | Purpose | Trigger | Runtime |
|----------|---------|---------|---------|
| `generate_lesson_content` | Create AI-powered lesson content | Step Functions workflow | Python 3.13 |
| `fix_lesson_markdown` | Clean and format lesson markdown | Step Functions workflow | Python 3.13 |
| `generate_multiple_choice_questions` | Generate MCQs from lesson content | Step Functions workflow | Python 3.13 |
| `generate_flashcards` | Create flashcards from lesson content | Step Functions workflow | Python 3.13 |

### **Content Retrieval Functions (4 Lambda Functions)**
| Function | Purpose | Trigger | Runtime |
|----------|---------|---------|---------|
| `get_lesson_content` | Retrieve lesson content from S3 | API Gateway GET /get-lesson-content | Python 3.13 |
| `get_multiple_choice_questions` | Get MCQs for a lesson | API Gateway GET /questions | Python 3.13 |
| `get_flashcards` | Retrieve flashcards for a lesson | API Gateway GET /flashcards | Python 3.13 |
| `get_image_data` | Fetch course/lesson images | API Gateway GET /get-image | Python 3.13 |

### **System Functions (4 Lambda Functions)**
| Function | Purpose | Trigger | Runtime |
|----------|---------|---------|---------|
| `extract_document_text` | Extract text from uploaded documents | File upload events | Python 3.13 |
| `mark_lesson_generated` | Mark lesson generation as completed | Step Functions workflow | Python 3.13 |
| `update_chapter_status` | Update chapter generation status | Step Functions workflow | Python 3.13 |
| `check_chapter_generation_status` | Monitor chapter generation progress | API Gateway GET /check-chapter-generation-status | Python 3.13 |
| `get_user_info` | Retrieve authenticated user details | API Gateway GET /auth/userinfo | Python 3.13 |

> **💡 Lambda Function Architecture Benefits:**
> - **Independent Scaling**: Each function scales based on its specific load
> - **Fault Isolation**: Failure in one function doesn't affect others
> - **Specialized Optimization**: Memory and timeout tuned per function workload
> - **Cost Efficiency**: Pay only for actual compute time used per function

---

## 🗄️ **AWS DynamoDB Tables**

### **CoursePlanTable**
- **Purpose**: Store course plans, chapters, lessons, and status tracking
- **Partition Key**: `CourseID` (String)
- **Sort Key**: `UserID` (String)
- **GSI**: `UserID-index` for user-specific queries
- **Data Structure**:
  ```json
  {
    "CourseID": "uuid",
    "UserID": "cognito-user-id",
    "title": "Course Title",
    "description": "Course Description",
    "chapters": [...],
    "chapters_status": {
      "chapter_id": {
        "lessons_status": "PENDING|GENERATING|COMPLETED|FAILED",
        "mcqs_status": "PENDING|GENERATING|COMPLETED|FAILED",
        "flashcards_status": "PENDING|GENERATING|COMPLETED|FAILED"
      }
    }
  }
  ```

### **FlashcardsTable**
- **Purpose**: Store individual flashcards for lessons
- **Partition Key**: `LessonFlashcardId` (String) - Format: `FLASHCARD#{course_id}#{chapter_id}#{lesson_id}`
- **Sort Key**: `CardId` (String) - Format: `CARD#01`, `CARD#02`, etc.
- **Data Structure**:
  ```json
  {
    "LessonFlashcardId": "FLASHCARD#course#chapter#lesson",
    "CardId": "CARD#01",
    "CourseID": "course_id",
    "ChapterID": "chapter_id",
    "LessonID": "lesson_id",
    "Question": "Flashcard question",
    "Answer": "Flashcard answer",
    "CardNumber": 1,
    "CreatedAt": "2024-01-15T10:30:00Z",
    "UserID": "user_id"
  }
  ```

---

## 🪣 **AWS S3 Buckets**

### **Lesson Content Bucket**
- **Purpose**: Store generated lesson content as JSON files
- **File Format**: `{courseId}-{chapterId}-{lessonId}.json`
- **Content Structure**: Dictionary of lesson sections with markdown content
- **Access**: Lambda functions have read/write permissions

### **Questions Bucket**
- **Purpose**: Store multiple-choice questions as JSON files
- **File Format**: `{courseId}-{chapterId}-{lessonId}-questions.json`
- **Content Structure**: Array of MCQ objects with questions, options, answers
- **Access**: Lambda functions have read/write permissions

### **Course Images Bucket**
- **Purpose**: Store AI-generated course cover images
- **File Format**: Various image formats (PNG, JPG)
- **Access**: Public read access for course images

---

## 🔄 **AWS Step Functions**

### **CourseGenerationStateMachine**
**Purpose**: Orchestrate the complete course content generation workflow

**Workflow Structure**:
```
1. Get Course Plan
2. Extract Chapter from Course Plan  
3. Mark Chapter as Generating
4. Generate Each Lesson in Chapter
5. Parallel Execution:
   ├── Save Chapter State (lessons_status → COMPLETED)
   ├── MCQs Branch:
   │   ├── Mark MCQs as Generating
   │   ├── Generate Questions for Each Lesson
   │   └── Save MCQ State to DynamoDB
   └── Flashcards Branch:
       ├── Mark Flashcards as Generating
       ├── Generate Flashcards for Each Lesson
       └── Save Flashcards State to DynamoDB
```

**Key Features**:
- **Parallel Processing**: MCQs and Flashcards generate simultaneously
- **Error Handling**: Retry logic and failure state management
- **Status Tracking**: Real-time updates to chapter status
- **Scalability**: Processes multiple lessons concurrently

---

## 🌐 **AWS API Gateway**

### **REST API Endpoints**

#### **Authentication (No Authorization Required)**
- `POST /auth/signup` - User registration
- `POST /auth/signin` - User login
- `POST /auth/verify-code` - Email verification
- `POST /auth/resend-verification-code` - Resend verification
- `POST /auth/refresh-token` - Token refresh

#### **Protected Endpoints (Cognito Authorization Required)**
- `POST /generate-course-plan` - Create new course
- `POST /generate-chapter` - Trigger chapter generation
- `GET /get-course-list` - List user's courses
- `GET /get-course-plan` - Get course details
- `GET /get-lesson-content` - Retrieve lesson content
- `GET /questions` - Get multiple-choice questions
- `GET /flashcards` - Get lesson flashcards
- `GET /get-image` - Retrieve course images
- `GET /check-chapter-generation-status` - Monitor generation progress
- `DELETE /delete-course` - Remove course
- `GET /auth/userinfo` - Get user information

### **API Gateway Features**
- **CORS Enabled**: Cross-origin requests supported
- **Cognito Integration**: JWT token validation
- **Rate Limiting**: Built-in request throttling
- **Request/Response Transformation**: Data formatting and validation

---

## 🔐 **AWS Cognito**

### **User Pool Configuration**
- **Authentication Flow**: Server-side auth with JWT tokens
- **User Attributes**: Email, username, custom attributes
- **Verification**: Email-based account verification
- **Security**: Password policies and MFA support

### **Integration with Lambda**
- **Authorizer**: Validates JWT tokens for protected endpoints
- **User Management**: Registration, login, verification flows
- **Token Management**: Access token refresh and validation

---

## 🤖 **AI/ML Integration**

### **Supported AI Providers**
1. **Google AI Studio (Gemini)**
   - Models: `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-2.5-pro`
   - Used for: Course generation, lesson content, MCQs, flashcards

2. **AWS Bedrock (Claude)**
   - Models: `claude-4-sonnet`, `claude-3.7-sonnet`, `claude-3.5-haiku`
   - Used for: Alternative AI processing and content generation

### **AI Function Integration**
- **Retry Logic**: Automatic fallback between AI providers
- **Rate Limiting**: Built-in handling for API limits
- **Error Handling**: Graceful degradation and error recovery
- **Structured Output**: JSON schema validation for consistent responses

---

## 🔧 **Infrastructure as Code (AWS CDK)**

### **CDK Stack Structure**
```python
LessonBuddyApiStack
├── Tables (DynamoDB)
├── Buckets (S3)
├── Authentication (Cognito)
├── Functions (Lambda)
└── ApiGateway (API Gateway + Routes)
```

### **Key CDK Features**
- **Environment Variables**: Automatic injection of resource ARNs
- **IAM Permissions**: Least-privilege access controls
- **Resource Dependencies**: Proper dependency management
- **Deployment**: Single command deployment with `cdk deploy`

---

## 🚀 **Deployment & CI/CD**

### **GitHub Workflow**
- **Trigger**: Push to main branch
- **Process**: 
  1. Install dependencies
  2. Run CDK synthesis
  3. Deploy to AWS
  4. Update Lambda functions
  5. Update API Gateway configuration

### **Environment Configuration**
- **Secrets Management**: GitHub secrets for API keys
- **Environment Variables**: Automatic injection via CDK
- **Region**: Configurable AWS region deployment

---

## 📊 **Monitoring & Logging**

### **CloudWatch Integration**
- **Lambda Logs**: Automatic logging for all functions
- **API Gateway Logs**: Request/response logging
- **Step Functions**: Execution tracking and debugging
- **DynamoDB Metrics**: Performance monitoring

### **Error Handling**
- **Retry Logic**: Built into Step Functions and Lambda
- **Dead Letter Queues**: For failed message processing
- **Alerting**: CloudWatch alarms for critical failures

---

## 🔒 **Security Features**

### **Authentication & Authorization**
- **JWT Tokens**: Secure API access
- **Cognito Integration**: Managed user authentication
- **IAM Roles**: Function-specific permissions
- **API Key Management**: Secure AI provider integration

### **Data Protection**
- **Encryption**: At-rest and in-transit encryption
- **Access Controls**: User-scoped data access
- **Input Validation**: Request sanitization and validation
- **CORS Configuration**: Controlled cross-origin access

---

## 🎯 **Key Architectural Decisions**

### **Serverless Architecture**
- **Benefits**: Auto-scaling, pay-per-use, minimal infrastructure management
- **Components**: Lambda, API Gateway, DynamoDB, S3
- **Cost Optimization**: Event-driven execution model

### **Microservices Design**
- **Single Responsibility**: Each Lambda function has one purpose
- **Loose Coupling**: Functions communicate via events and APIs
- **Independent Deployment**: Functions can be updated independently

### **Event-Driven Processing**
- **Step Functions**: Orchestrate complex workflows
- **Parallel Processing**: MCQs and flashcards generate simultaneously
- **Asynchronous Operations**: Non-blocking content generation

### **Data Storage Strategy**
- **DynamoDB**: NoSQL for fast, scalable data access
- **S3**: Object storage for large content files
- **Structured Data**: Consistent schema across all components

---

## 🛠️ **Development Guidelines**

### **Adding New Lambda Functions**
1. Create function directory in `lesson_buddy_api/functions/`
2. Add function to `Functions` class in `__init__.py`
3. Configure IAM permissions and environment variables
4. Add API Gateway route if needed
5. Update Step Functions workflow if applicable

### **Modifying Existing Functions**
1. Update function code
2. Test locally with sample events
3. Deploy via GitHub workflow
4. Monitor CloudWatch logs for issues

### **Database Schema Changes**
1. Update table definitions in `lesson_buddy_api/tables/`
2. Consider migration strategy for existing data
3. Update Lambda functions that interact with changed tables
4. Test data integrity after deployment

---

## 📈 **Performance Considerations**

### **Lambda Optimizations**
- **Memory Allocation**: Tuned per function workload
- **Timeout Configuration**: Balanced for performance vs. cost
- **Cold Start Mitigation**: Proper runtime selection and initialization

### **DynamoDB Performance**
- **Partition Key Design**: Optimized for access patterns
- **GSI Strategy**: Efficient secondary access patterns
- **Batch Operations**: Bulk read/write operations where possible

### **S3 Performance**
- **Object Naming**: Optimized for access patterns
- **Transfer Acceleration**: For global content delivery
- **Lifecycle Policies**: Automated storage class transitions

---

## 🔍 **Troubleshooting Guide**

### **Common Issues**
1. **Lambda Timeout**: Increase timeout or optimize code
2. **DynamoDB Access Denied**: Check IAM permissions
3. **API Gateway 500 Errors**: Check Lambda function logs
4. **Step Functions Failed**: Review execution history and logs

### **Debugging Tools**
- **CloudWatch Logs**: Function execution details
- **X-Ray Tracing**: Request flow visualization
- **Step Functions Console**: Workflow execution monitoring
- **API Gateway Test Console**: Endpoint testing

---

## 📚 **Additional Resources**

- **AWS CDK Documentation**: https://docs.aws.amazon.com/cdk/
- **AWS Lambda Best Practices**: https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html
- **DynamoDB Design Patterns**: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html
- **Step Functions Workflows**: https://docs.aws.amazon.com/step-functions/latest/dg/concepts-workflows.html

---

*This guide provides a comprehensive overview of the VEDIRA API architecture. For specific implementation details, refer to the code comments and AWS service documentation.* 