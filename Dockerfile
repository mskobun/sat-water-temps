FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY static/ ${LAMBDA_TASK_ROOT}/static/
COPY lambda_functions/ ${LAMBDA_TASK_ROOT}/

CMD ["initiator.handler"]
