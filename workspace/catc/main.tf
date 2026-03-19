terraform {
  required_providers {
    catalystcenter = {
      source  = "CiscoDevNet/catalystcenter"
      version = "0.4.6"
    }
  }
}

provider "catalystcenter" {
  username    = "admin"
  password    = "C1sco12345"
  url         = "https://64.103.47.49"
  max_timeout = 600
}

module "catalyst_center" {
  source  = "netascode/nac-catalystcenter/catalystcenter"
  version = "0.3.0"

  yaml_directories      = ["data/", "data2/"]
  templates_directories = ["data/templates/", "data2/templates/"]

  use_bulk_api = true
}