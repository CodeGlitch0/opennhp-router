module github.com/opennhp-router/authclient

go 1.26.0

require (
	github.com/OpenNHP/opennhp/nhp v0.6.0
	github.com/pelletier/go-toml/v2 v2.4.3
)

// Overridden in the server image to the pinned clone at /src/opennhp/nhp.
replace github.com/OpenNHP/opennhp/nhp => /src/opennhp/nhp
