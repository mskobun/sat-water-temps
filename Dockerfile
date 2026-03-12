FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12

# Required for Python XML/geospatial deps (e.g. rasterio) at runtime
RUN dnf install -y expat && dnf clean all

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY static/ ${LAMBDA_TASK_ROOT}/static/
COPY lambda_functions/ ${LAMBDA_TASK_ROOT}/

CMD ["initiator.handler"]
