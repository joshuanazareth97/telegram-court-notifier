# Use an official Python runtime as a parent image
FROM python:3.8-slim-buster

# Set the working directory to /app
WORKDIR /app

# Copy the Pipfile and Pipfile.lock to the container
COPY ../Pipfile* ./

# Install Pipenv
RUN pip install --no-cache-dir pipenv

# Install the dependencies specified in the Pipfile
RUN pipenv install --deploy --system

# Copy the rest of the application code into the container
COPY . .

# Run the command to start the application
CMD ["python", "bot.py"]
