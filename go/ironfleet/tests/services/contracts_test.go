package services

import (
	"ironfleet/shared/contracts"
	"testing"
)

func TestServiceContractRoundTrip(t *testing.T) {
	if contracts.Contracts["gateway"]["id"] != "gateway" {
		t.Fatal("missing gateway contract")
	}
	if contracts.Contracts["routing"]["port"].(int) <= 0 {
		t.Fatal("invalid routing port")
	}
}
