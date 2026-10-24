terraform {
  required_version = ">= 1.6.0"

  # Explicit local backend.
  #
  # Declaring it (instead of relying on the implicit one) allows pointing the
  # state at a different file with `terraform init -backend-config="path=..."`.
  # That is how the local emulator (Floci) keeps its own state file, separate
  # from the one a real AWS deployment would use.
  #
  # To switch to the remote backend, replace this block with the one from
  # `backend.tf.example` and run `terraform init`.
  backend "local" {
    path = "terraform.tfstate"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
