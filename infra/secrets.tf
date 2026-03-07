resource "google_secret_manager_secret" "db_password" {
  secret_id = "shell-chat-db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

resource "google_secret_manager_secret" "together_api_key" {
  secret_id = "together-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "together_api_key" {
  secret      = google_secret_manager_secret.together_api_key.id
  secret_data = var.together_api_key
}
