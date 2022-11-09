# External networking
variable "external_network" {
  type = object({
    cidr             = string
    start            = string
    end              = string
    physical_network = string
    network_type     = string
    segmentation_id  = number
  })
}


# User setup
variable "user" {
  type = object({
    username = string
    password = string
    cidr     = string
  })
  sensitive = true
}
