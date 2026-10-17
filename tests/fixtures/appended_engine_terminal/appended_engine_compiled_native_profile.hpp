// TEST ONLY: synthetic nonzero source identities are not retained-engine pins.
#pragma once
#include "shared/native_engine_loader.hpp"
namespace foundation::appended {
// const view permits the fixture to select malformed compiled facts before main.
#if defined(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE) && FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
inline const engine_document_actions::EngineDocumentActionsProfileFacts& compiled_native_engine_document_actions_profile=terminal_main_fixture::state.actions_profile;
inline NativeEngineLoadPlan compiled_native_engine_load_plan(const std::filesystem::path& root) {
    auto& s=terminal_main_fixture::state;++s.plans;terminal_main_fixture::event("plan");
    NativeEngineLoadPlan p;p.root=root;s.plan_root=root.string();
    if(terminal_main_fixture::is("plan-root"))p.root=root/"other";
    auto& e=p.expectation;e.document_actions_profile=s.actions_profile;
    if(s.actions_mismatch>=0&&s.actions_mismatch<=90)terminal_main_fixture::alter_actions(e.document_actions_profile,s.actions_mismatch);
    e.target_system=s.actions_profile.target_system;e.target_processor=s.actions_profile.target_processor;e.pointer_bits=s.actions_profile.pointer_bits;
    e.contract_header_sha256=s.actions_profile.contract_sha256;e.build_identity_sha256=s.actions_profile.build_sha256;e.source_recipe_sha256=s.actions_profile.source_recipe_sha256;
    switch(s.actions_mismatch){case 91:++e.target_system;break;case 92:++e.target_processor;break;case 93:++e.pointer_bits;break;
    case 94:e.contract_header_sha256[0]^=1;break;case 95:e.build_identity_sha256[0]^=1;break;case 96:e.source_recipe_sha256[0]^=1;break;default:break;}
    if(terminal_main_fixture::is("actions-legacy-document"))e.document_profile=s.profile;
    if(terminal_main_fixture::is("actions-legacy-editor"))e.editor_profile.enabled=true;
    if(terminal_main_fixture::is("actions-legacy-document-dirty"))e.document_profile.name="inactive-but-dirty";
    if(terminal_main_fixture::is("actions-legacy-editor-dirty"))e.editor_profile.name="inactive-but-dirty";
    return p;
}
#else
inline const engine_document::EngineDocumentProfileFacts& compiled_native_engine_document_profile=terminal_main_fixture::state.profile;
inline NativeEngineLoadPlan compiled_native_engine_load_plan(const std::filesystem::path& root) {
    auto& s=terminal_main_fixture::state;++s.plans;terminal_main_fixture::event("plan");
    NativeEngineLoadPlan p;p.root=root;s.plan_root=root.string();
    if(terminal_main_fixture::is("plan-root"))p.root=root/"other";
    p.expectation.document_profile=s.profile;auto& f=p.expectation.document_profile;
    switch(s.mismatch){
    case 0:f.enabled=false;break;case 1:f.kind=engine_document::ProfileKind::physical;break;
    case 2:f.name+="x";break;case 3:++f.provider_abi_major;break;case 4:++f.provider_abi_minor;break;
    case 5:++f.host_abi_major;break;case 6:++f.host_abi_minor;break;case 7:++f.target_system;break;
    case 8:++f.target_processor;break;case 9:++f.pointer_bits;break;case 10:++f.lifetime;break;
    case 11:++f.maximum_starts;break;case 12:++f.viewport_width;break;case 13:++f.viewport_height;break;
    case 14:++f.provider_capabilities;break;case 15:f.base_header_sha256[0]^=1;break;
    case 16:f.extension_header_sha256[0]^=1;break;case 17:f.contract_sha256[0]^=1;break;
    case 18:f.catalog_sha256[0]^=1;break;case 19:f.build_sha256[0]^=1;break;
    case 20:f.source_recipe_sha256[0]^=1;break;case 21:f.physical_catalog_sha256[0]=1;break;
    case 22:++f.queries[0].operation;break;case 23:++f.queries[0].maximum_input_bytes;break;
    case 24:++f.queries[0].required_reply_capacity;break;case 25:++f.queries[0].capability;break;
    case 26:f.queries[0].schema_sha256[0]^=1;break;case 27:++f.commands[0].operation;break;
    case 28:++f.commands[1].required_reply_capacity;break;case 29:++f.query_count;break;case 30:++f.command_count;break;
    default:break;
    }
    auto& e=p.expectation;e.target_system=s.profile.target_system;e.target_processor=s.profile.target_processor;e.pointer_bits=s.profile.pointer_bits;
    e.contract_header_sha256=s.profile.contract_sha256;e.build_identity_sha256=s.profile.build_sha256;e.source_recipe_sha256=s.profile.source_recipe_sha256;
    switch(s.mismatch){case 31:++e.target_system;break;case 32:++e.target_processor;break;case 33:++e.pointer_bits;break;
    case 34:e.contract_header_sha256[0]^=1;break;case 35:e.build_identity_sha256[0]^=1;break;case 36:e.source_recipe_sha256[0]^=1;break;default:break;}
    return p;
}
#endif
}
