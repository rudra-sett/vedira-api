# VEDIRA - Your Lesson Buddy

## 🚀 **Overview**

**VEDIRA API** is the **serverless backend** that powers the VEDIRA educational platform. **AWS Lambda is the core compute foundation** - with **22 specialized Lambda functions** handling all business logic, from user authentication to AI-powered content generation. This repo serves the [**VEDIRA Flutter mobile app**](https://github.com/DB-25/vedira) with a completely serverless, event-driven architecture.

> **🔗 Frontend Repository**: [`vedira`](https://github.com/DB-25/vedira) - Flutter mobile application  
> **🔗 Backend Repository**: `vedira-api` - This serverless API (current repository)

---

## 🏗️ **Architecture**

- **🚀 22 AWS Lambda Functions** - All business logic runs serverlessly
- **🔄 AWS Step Functions** - Orchestrate complex content generation workflows
- **🌐 API Gateway** - RESTful endpoints serving the mobile app
- **🗄️ DynamoDB + S3** - Scalable data storage
- **🤖 AI Integration** - Multi-provider AI content generation

---

## 🛠️ **AWS Services Used**

### **Core Compute & Orchestration**
- **AWS Lambda** (22 functions) - Authentication, course management, AI content generation
- **AWS Step Functions** - Multi-step workflow orchestration
- **API Gateway** - HTTP API endpoints

### **Data & Storage**
- **DynamoDB** (2 tables) - Course plans and flashcards
- **S3** (3 buckets) - Lesson content, questions, course images
- **Cognito** - User authentication and JWT management

### **Infrastructure & Monitoring**
- **AWS CDK** - Infrastructure as Code
- **CloudWatch** - Logging and monitoring
- **IAM** - Security and permissions

### **AI & External Integration**
- **AWS Bedrock** - Claude AI models
- **External AI APIs** - Google AI Studio (Gemini) integration

---

## ✨ **Key Features**

- **🎓 AI-Powered Course Generation** - Create personalized learning content
- **🔐 Complete Authentication System** - User registration, login, verification
- **📚 Course Management** - CRUD operations for educational content
- **⚡ Serverless Architecture** - Auto-scaling, cost-effective, high availability
- **📱 Mobile API** - Optimized endpoints for Flutter mobile app

---

## 🚀 **Quick Start**

### **Prerequisites**
- AWS CLI configured
- AWS CDK installed (`npm install -g aws-cdk`)
- Python 3.13+

### **Deploy**
```bash
git clone https://github.com/rudra-sett/vedira-api.git
cd vedira-api
pip install -r requirements.txt
cdk deploy
```

### **Environment Variables**
```bash
API_KEY=your_google_ai_studio_key
BEDROCK_API_KEY=your_aws_bedrock_key
```

---

## 📚 **Complete Documentation**

For detailed technical documentation, architecture decisions, Lambda function specifications, and implementation guides:

**📖 [REPOGUIDE.md](./REPOGUIDE.md)** - Comprehensive technical documentation

---

## 🔗 **Related Repositories**

- **[vedira](https://github.com/DB-25/vedira)** - Flutter mobile application frontend
- **[vedira-api](https://github.com/rudra-sett/vedira-api)** - This serverless backend API

---

*Serverless educational platform built with AWS Lambda*

Please note that you will see references to "Lesson Buddy" in this repository; this was an old name before we renamed our product to Vedira.
