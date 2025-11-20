FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.9

# Install system dependencies (gcc for some builds, but relying on wheels mostly)
RUN yum install -y gcc-c++ libcurl-devel

# Upgrade pip to ensure we can find the latest wheels
RUN pip install --upgrade pip

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy static files (ROI GeoJSON)
COPY static/ ${LAMBDA_TASK_ROOT}/static/

# Copy Lambda function code
COPY lambda_functions/ ${LAMBDA_TASK_ROOT}/

# Set the CMD to your handler (this will be overridden by the Lambda configuration)
CMD ["initiator.handler"]
