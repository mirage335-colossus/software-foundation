// Private nonproduction maintenance harness. No retained SDK admission occurs.
#pragma once
#include "native_engine_driver.hpp"
#include <cstdint>
#include <iosfwd>
#include <span>
#include <string>

namespace foundation::appended::raw_candidate {
using Factory = decltype(&bib_engine_get_provider_v1);
struct PackageInput {
    std::uint64_t index_offset{}, index_length{};
    std::string sha256; // Independent controller pin, not a provider assertion.
};
struct RawCandidateRuntimeObservations {
    std::uint64_t getter_calls{}, starts{}, rejected_second_starts{}, provider_entries{}, maximum_provider_depth{};
    std::uint64_t enter_calls{}, leave_calls{}, outside_owner_samples{}, query3_calls{}, query3_reply_bytes{}, semantic_revision{};
    std::uint64_t echo_calls{}, echo_request_bytes{}, echo_reply_bytes{}, service_ack_through{}, deliveries{};
    std::uint64_t damage_callbacks{}, frame_revision{}, opaque_pixels{}, differing_pixels{};
    std::uint64_t application_instance{}, document_sequence{}, service_generation{}, snapshot_revision{}, marker_observations{};
    std::uint64_t final_state{};
    std::string frame_sha256, query3_sha256;
};
// Constructs exact maintained4083 facts from independent target/R/B inputs.
NativeEngineExpectation document_actions_expectation(std::uint32_t system, std::uint32_t processor,
    const engine_document::Digest& recipe, const engine_document::Digest& build);
// Uses the same public ABI, checked table, Package reader, Owner, Driver,
// document composition, TerminalAdapter and application demo.echo handler.
// One process only; all callback/provider state is retained until process exit.
RawCandidateRuntimeObservations run_raw_candidate_offscreen_probe(Factory,
    const NativeEngineExpectation&, std::span<const std::uint8_t> package_bytes, const PackageInput&);
void write_observations_json(std::ostream&, const RawCandidateRuntimeObservations&);
} // namespace foundation::appended::raw_candidate
