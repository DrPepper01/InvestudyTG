{% if False %}

# Introduction

This is a simple Django project for a Telegram support bot. The bot allows users to report issues, send screenshots, and receive assistance from the support team.

!(https://t.me/Investudy_support_bot)

### Main features

* User Issue Handling: The bot accepts user submissions and saves them to the database.

* Multi-step Conversation: Implements a sequential information gathering from users using ConversationHandler.

* Screenshot Reception: Users can attach screenshots or photos to illustrate their issues.

* Support Team Notifications: The bot sends information about new submissions to a designated support chat.

* Django Integration: Utilizes Django for data management and administration.

* Docker Containerization: The project is packaged with Docker for easy deployment.


# Getting Started

Follow these instructions to get a copy of the project up and running on your local machine for development and testing purposes:

### Prerequisites

Ensure you have the following installed:

* Git
* Docker
* Docker Compose
    
### Installation

      git clone git@github.com:DrPepper01/InvestudyTG.git
      cd InvestudyTG
      
### Create an Environment Variables File

Create a .env file in the root directory of the project and add the necessary variables:
	POSTGRES_DB=your_db_name
	POSTGRES_USER=your_db_user
	POSTGRES_PASSWORD=your_db_password
	TELEGRAM_BOT_TOKEN=your_telegram_bot_token
	SUPPORT_CHAT_ID=your_support_chat_id
* TELEGRAM_BOT_TOKEN: Your Telegram bot token obtained from @BotFather.
* SUPPORT_CHAT_ID: The ID of the support chat where the bot will send notifications.

### Build and Start Docker Containers

Run the following command to build and start the containers:

	docker-compose up --build

This command will start three services:

* db: The PostgreSQL database container.
* web: The Django application container.
* bot: The Telegram bot container.

### Apply Migrations

In a new terminal window, apply the database migrations:

	docker-compose exec web python manage.py migrate

### Create a Superuser

If you need access to the Django admin panel, create a superuser:

	docker-compose exec web python manage.py createsuperuser

### Access the Application

Web Application: Visit http://localhost:8002
Django Admin Panel: Visit http://localhost:8002/admin/
Telegram Bot: Find and start a conversation with @{your_bot_name}

# Usage
Submitting an Issue

* Users can start a conversation with the bot by sending the /start command. The bot will guide them through a series of questions to gather the necessary information.

* Receiving Notifications

### Project Structure

* Dockerfile: Defines the Docker image for the application.
* docker-compose.yml: Docker Compose configuration to run multiple services.
* ProjectTG/: Directory containing Django project settings.
* tg_app/: Django app with models and bot logic.
* requirements.txt: List of Python dependencies.

### Additional Information
Data Models

	UserProfile: Stores information about Telegram users.
	Ticket: Represents a user's submission or issue.
	Attachment: Saves user attachments (e.g., screenshots).
	
### Environment Variables
	Ensure that secret keys and tokens are not added to version control. Always use environment variables or files not tracked by Git.
Ensure that secret keys and tokens are not added to version control. Always use environment variables or files not tracked by Git.

### Example .env File

	POSTGRES_DB=your_db
	POSTGRES_USER=your_user
	POSTGRES_PASSWORD=secure_password
	TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ
	SUPPORT_CHAT_ID=-1001234567890

### Contact 

If you have any questions or suggestions, please contact us at bekzatablaev@gmail.com

# Additional Instructions

If you encounter issues running the project, here are some additional troubleshooting steps.

Checking Container Status
To verify that all containers are running correctly, execute:

	docker-compose ps


Viewing Logs
You can view logs for a specific service:

	docker-compose logs web
	docker-compose logs bot
	docker-compose logs db
	
Stopping Containers
To stop all containers:

	docker-compose down

Rebuilding Containers
If you've made changes to the code and need to rebuild the containers:

	docker-compose up --build

Updating Dependencies
If you've added new dependencies to requirements.txt, rebuild the containers to install them.

I hope this information helps you successfully launch and use the project!
