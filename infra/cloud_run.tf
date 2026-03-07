resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "shell-chat"
  format        = "DOCKER"
  description   = "Shell Chat container images"

  depends_on = [google_project_service.apis]
}

locals {
  image          = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}/shell-chat-backend"
  connection_name = google_sql_database_instance.main.connection_name
  database_url   = "postgresql://${google_sql_user.app.name}:${random_password.db_password.result}@/${google_sql_database.navigator.name}?host=/cloudsql/${local.connection_name}"
}

resource "google_cloud_run_v2_service" "backend" {
  name     = "shell-chat-backend"
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [local.connection_name]
      }
    }

    containers {
      image = "${local.image}:latest"

      ports {
        container_port = 8000
      }

      resources {
        cpu_idle = true
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
      }

      env {
        name  = "DATABASE_URL"
        value = local.database_url
      }

      env {
        name  = "FIREBASE_PROJECT_ID"
        value = var.firebase_project_id
      }

      env {
        name = "TOGETHER_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.together_api_key.secret_id
            version = "latest"
          }
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_version.together_api_key,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.backend.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
