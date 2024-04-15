# Use an official Python runtime as a parent image
FROM python:3.8-slim-buster


# Set the working directory to /app
WORKDIR /app

# Copy the Pipfile and Pipfile.lock to the container
COPY pyproject.toml /app/

# Install Poetry
RUN pip install --user poetry
ENV PATH="${PATH}:/root/.local/bin"
RUN poetry config virtualenvs.create false

# Install the dependencies specified in the Pipfile
RUN poetry install --no-interaction --no-ansi

# Copy the rest of the application code into the container
COPY . .

# Run the command to start the application
CMD ["python", "bot.py"]
