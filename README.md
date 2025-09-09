# SyncScope Management Service

Team and project management service for the SyncScope platform.

## 🎯 Overview

The Management Service handles:
- **Team Management**: Create and manage development teams
- **Project Management**: Organize projects within teams  
- **Member Management**: Manage team memberships and roles
- **Integration Management**: Connect projects with external services (GitHub, Slack, etc.)
- **GitHub Integration**: Sync repositories, commits, and pull requests

## 🏗️ Architecture

- **Framework**: Django + Django REST Framework
- **Database**: PostgreSQL (management schema)
- **Authentication**: Remote JWT via Auth Service
- **API Documentation**: OpenAPI/Swagger with drf-spectacular
- **Deployment**: Railway

## 📊 Database Schema

The service uses the `management` schema with these main entities:
- `teams` - Development teams
- `projects` - Projects within teams
- `team_members` - Team membership and roles
- `integrations` - External service integrations
- `github_integrations` - GitHub-specific integration data
- `code_commits` - Commit history from integrated repositories

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis (optional)
- Auth Service running

### Local Development

1. **Clone and Setup**
```bash
git clone <repo-url>
cd syncscope-management-service
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

2. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Database Setup**
```bash
python manage.py migrate
```

4. **Run Server**
```bash
python manage.py runserver 8003
```

### Docker Development

```bash
docker build -t management-service .
docker run -p 8003:8000 --env-file .env management-service
```

## 🔌 API Endpoints

### Teams
- `GET /management/api/teams/` - List teams
- `POST /management/api/teams/` - Create team
- `GET /management/api/teams/{id}/` - Get team details
- `PUT /management/api/teams/{id}/` - Update team
- `DELETE /management/api/teams/{id}/` - Delete team
- `GET /management/api/teams/{id}/members/` - Get team members
- `POST /management/api/teams/{id}/members/` - Add team member
- `GET /management/api/teams/{id}/projects/` - Get team projects

### Projects
- `GET /management/api/projects/` - List projects
- `POST /management/api/projects/` - Create project
- `GET /management/api/projects/{id}/` - Get project details
- `PUT /management/api/projects/{id}/` - Update project
- `DELETE /management/api/projects/{id}/` - Delete project
- `GET /management/api/projects/{id}/integrations/` - Get project integrations
- `POST /management/api/projects/{id}/integrations/` - Create integration
- `GET /management/api/projects/{id}/commits/` - Get project commits

### Team Members
- `GET /management/api/team-members/` - List team members
- `GET /management/api/team-members/{id}/` - Get member details
- `PUT /management/api/team-members/{id}/` - Update member
- `DELETE /management/api/team-members/{id}/` - Remove member

### Integrations
- `GET /management/api/integrations/` - List integrations
- `GET /management/api/integrations/{id}/` - Get integration details
- `PUT /management/api/integrations/{id}/` - Update integration
- `DELETE /management/api/integrations/{id}/` - Delete integration

### GitHub Integrations
- `GET /management/api/github-integrations/` - List GitHub integrations
- `POST /management/api/github-integrations/` - Create GitHub integration
- `GET /management/api/github-integrations/{id}/` - Get GitHub integration
- `POST /management/api/github-integrations/{id}/sync/` - Trigger manual sync

### Health Checks
- `GET /health/` - Service health status
- `GET /health/ready/` - Readiness probe
- `GET /health/live/` - Liveness probe

## 🔐 Authentication & Authorization

### Remote Authentication
The service uses JWT tokens validated against the Auth Service:
```bash
curl -H "Authorization: Bearer <jwt-token>" \
     http://localhost:8003/management/api/teams/
```

### Role-Based Permissions
- **Admin**: Full access to all resources
- **Team Lead**: Manage team resources and members
- **Developer**: Read access to team resources

### Permission Classes
- `IsOwnerOrAdmin` - Team operations
- `IsTeamMemberOrAdmin` - Team member operations  
- `IsProjectMemberOrAdmin` - Project operations

## 🧪 Testing

### Run Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=apps.management

# Specific test file
pytest tests/test_models.py

# Run with settings
pytest --ds=config.test_settings
```

### Test Coverage
The project maintains ≥80% test coverage with comprehensive tests for:
- Models and relationships
- API views and permissions
- Authentication and authorization
- Serializers and validation
- Admin interface

## 🔧 Configuration

### Environment Variables
```bash
# Database
DB_HOST=localhost
DB_NAME=syncscope
DB_USER=postgres
DB_PASSWORD=password
DB_PORT=5432

# Services
AUTH_SERVICE_URL=http://localhost:8001
MONITORING_SERVICE_URL=http://localhost:8002

# GitHub Integration
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# Management Service Limits
MAX_TEAM_MEMBERS=100
MAX_PROJECTS_PER_TEAM=50
MAX_INTEGRATIONS_PER_PROJECT=10
```

## 📋 Models

### Team
```python
class Team(models.Model):
    name = CharField(max_length=255)
    description = TextField(null=True, blank=True)
    company_id = UUIDField()  # Reference to auth.companies
    created_by = UUIDField()  # Reference to auth.users
```

### Project  
```python
class Project(models.Model):
    name = CharField(max_length=255)
    description = TextField(null=True, blank=True)
    team = ForeignKey(Team)
    repository_url = URLField(null=True)
    url = URLField(null=True)
```

### TeamMember
```python
class TeamMember(models.Model):
    team = ForeignKey(Team)
    user_id = UUIDField()  # Reference to auth.users
    role = CharField(choices=ROLE_CHOICES, default="developer")
    joined_at = DateTimeField(default=timezone.now)
```

## 🚀 Deployment

### Railway Deployment
The service is configured for Railway deployment with:
- Dockerfile for containerization
- Gunicorn WSGI server
- Health check endpoints
- Static file collection
- Database migrations

### Environment-Specific Settings
- **Production**: Optimized worker count, extended timeouts
- **Development**: Single worker, reload enabled
- **QA**: Balanced configuration for testing

## 🔍 Monitoring

### Health Endpoints
- `/health/` - Comprehensive health check with database and cache status
- `/health/ready/` - Readiness check for load balancers
- `/health/live/` - Simple liveness check

### Logging
Structured logging with:
- Request/response logging
- Database query logging
- Authentication events
- Integration sync events

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass and coverage ≥80%
5. Submit a pull request

### Code Style
- Black for code formatting
- isort for import sorting
- Comprehensive docstrings
- Type hints where applicable

### Testing Requirements
- Unit tests for all new functionality
- Integration tests for API endpoints
- Authentication/permission tests
- Maintain ≥80% coverage

## 📚 API Documentation

- **Swagger UI**: `/api/docs/`
- **ReDoc**: `/api/redoc/`
- **OpenAPI Schema**: `/api/schema/`

## 🔗 Service Dependencies

- **Auth Service**: User authentication and authorization
- **PostgreSQL**: Primary database with management schema
- **Redis**: Caching and session storage (optional)
- **GitHub API**: Repository integration and webhooks

## 📈 Version History

- **1.0.0**: Initial release with core team/project management
- Future releases will include advanced integrations and analytics

## 📞 Support

For issues and questions:
- Create GitHub issues for bugs and features
- Follow existing code patterns and conventions
- Ensure comprehensive test coverage
