terraform {
  backend "s3" {
    bucket       = "eco-water-temps-tf-state-240232487020"
    key          = "terraform.tfstate"
    region       = "us-west-2"
    use_lockfile = true
    encrypt      = true
  }
}
