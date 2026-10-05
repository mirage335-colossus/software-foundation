"""Small source-checked reading guides for dense edit-path examples.

These are curated explanations of known declarations, not invented signatures
inferred from punctuation. Full declaration anchors detect field-order drift.
The examples are illustrative source fragments; generation never executes them.
"""
from __future__ import annotations


def make_parameter_guides(ref) -> dict[str, dict]:
    def field(position, name, type_, description, default, example_value):
        return dict(position=position, name=name, type=type_, description=description,
                    default=default, example_value=example_value)

    def guide(id, title, summary, syntax, syntax_note, parameters, label, code, notes, references):
        return dict(id=id, title=title, summary=summary, syntax=syntax,
                    syntax_note=syntax_note, parameters=parameters,
                    example=dict(label=label, code=code, notes=notes), references=references,
                    status='verified' if all(r['status'] == 'verified' for r in references) else 'missing')

    no_default = 'No member initializer; specify explicitly in this recipe.'
    contract = '@gui-boundary/include/gui/contract.hpp'
    view = guide(
        'view-definition', 'ViewDefinition: the widget row, field by field',
        'Each top-level comma advances to the next struct field. The empty strings are different fields, not interchangeable padding.',
        'ViewDefinition{ id, kind, height, text, label, placeholder,\n'
        '                [bold, [wrap, [remove_extension]]] }',
        'Reading notation, not C++ to paste: square brackets mean optional trailing fields. '
        'The filled example below is a C++ aggregate expression. The first six fields stay explicit in this recipe.',
        [
            field(1, 'id', 'std::string_view', 'Stable widget identity; use the same ID when routing events.', no_default, '"entries.custom"'),
            field(2, 'kind', 'gui::Kind', 'Which supported control to create. This example creates a button.', no_default, 'gui::Kind::button'),
            field(3, 'height', 'double', 'Fixed row height in shared logical units; 0 makes a zero-height leaf in this layout.', no_default, '32'),
            field(4, 'text', 'std::string_view', 'Initial state.text, such as label content or editor contents.', no_default, '""'),
            field(5, 'label', 'std::string_view', 'Initial state.label; the button caption in this example.', no_default, '"Run custom action"'),
            field(6, 'placeholder', 'std::string_view', 'Hint for an empty editor or another control that supports it.', no_default, '""'),
            field(7, 'bold', 'bool', 'Initial font weight.', 'false', 'false'),
            field(8, 'wrap', 'gui::TextWrap', 'Text wrapping mode for text that uses shared measurement.', 'gui::TextWrap::none', 'gui::TextWrap::none'),
            field(9, 'remove_extension', 'bool', 'Reserve for the existing optional Remove feature; ordinary controls use false.', 'false', 'false'),
        ],
        'Filled example: an ordinary button row (illustrative new ID)',
        'ViewDefinition{\n'
        '    "entries.custom",      // 1. id\n'
        '    gui::Kind::button,      // 2. kind\n'
        '    32,                     // 3. height\n'
        '    "",                     // 4. text\n'
        '    "Run custom action",    // 5. label\n'
        '    "",                     // 6. placeholder\n'
        '    false,                  // 7. bold\n'
        '    gui::TextWrap::none,     // 8. wrap\n'
        '    false                   // 9. remove_extension\n'
        '}',
        ['Insert this expression as an element of view_definition, with a separating comma as needed. It does not implement the click handler.',
         'The three trailing values may be omitted to use their declared defaults. C++ can also value-initialize earlier omitted fields, but an empty ID is not a valid widget identity.',
         'This is the current nine-field schema. It has no page or parent field; those are explicit proposed additions in the tab edit path.',
         'gui::Kind::button is a scoped enum value, not another parameter. The two colons qualify its name; commas separate aggregate fields.'],
        [ref('Complete current ViewDefinition field order', 'gui/shared/view_definition.hpp',
             'struct ViewDefinition {\n    std::string_view id;\n    gui::Kind kind;\n    double height;\n'
             '    std::string_view text, label, placeholder;\n    bool bold = false;\n'
             '    gui::TextWrap wrap = gui::TextWrap::none;\n    bool remove_extension = false;\n};'),
         ref('Existing filled button row', 'gui/shared/view_definition.hpp',
             'ViewDefinition{"entries.add", gui::Kind::button, 32, "", "Add entry", ""}')])

    page = guide(
        'page', 'gui::Page: a tab ID, caption, and availability',
        'A Page describes one tab. Page IDs are for membership and events; labels are for people reading the tab bar.',
        'gui::Page{ id, label, [enabled, [visible]] }',
        'Reading notation: square brackets mark optional trailing values, not literal C++ brackets. All four fields are filled below.',
        [
            field(1, 'id', 'std::string', 'Unique nonempty page ID, used by active_page and WidgetSpec.page.', no_default, '"settings"'),
            field(2, 'label', 'std::string', 'Human-readable tab caption.', no_default, '"Settings"'),
            field(3, 'enabled', 'bool', 'Whether the page is available for selection.', 'true', 'true'),
            field(4, 'visible', 'bool', 'Whether the page is available for display in the tab bar.', 'true', 'true'),
        ],
        'Filled example: declare two pages and select the initial page',
        'view_.pages = {\n'
        '    gui::Page{\n'
        '        "entries",   // 1. id\n'
        '        "Entries",   // 2. label\n'
        '        true,        // 3. enabled\n'
        '        true         // 4. visible\n'
        '    },\n'
        '    gui::Page{\n'
        '        "settings",  // 1. id\n'
        '        "Settings",  // 2. label\n'
        '        true,        // 3. enabled\n'
        '        true         // 4. visible\n'
        '    }\n'
        '};\n'
        'view_.active_page = "entries";  // select by ID',
        ['This is a proposed constructor fragment. The current application does not initialize pages.',
         'Declaring a page is only one edit: assign its widget membership, reserve page_bar geometry, and handle PageEvent as shown in the tab path.',
         'enabled and visible are independent. A page event for an unavailable page is rejected by normalization.'],
        [ref('Complete retained Page declaration', contract,
             'struct Page {\n    std::string id,label;\n    bool enabled=true,visible=true;\n'
             '    bool operator==(const Page&) const = default;\n};'),
         ref('Retained page initialization example', '@gui-boundary/examples/application.hpp',
             'view_.pages={{"main","Controls"},{"other","Other page"}};view_.active_page="main";')])

    rect = guide(
        'rect', 'gui::Rect: left, top, width, and height',
        'For page_bar and widget bounds, Rect uses logical client coordinates. The last two fields are extents, not the right and bottom edges.',
        'gui::Rect{ x, y, width, height }',
        'The names indicate positional fields; replace them with values. This also explains an untyped brace list assigned to page_bar or bounds.',
        [
            field(1, 'x', 'double', 'Left edge; for this page_bar example, measured from the client area\'s left edge.', '0', '16'),
            field(2, 'y', 'double', 'Top edge; for this page_bar example, measured from the client area\'s top edge.', '0', '448'),
            field(3, 'width', 'double', 'Horizontal extent; 608 means right edge is 16 + 608 = 624.', '0', '608'),
            field(4, 'height', 'double', 'Vertical extent; 24 means bottom edge is 448 + 24 = 472.', '0', '24'),
        ],
        'Filled example: a tab bar for a 640 by 480 client area',
        'next.page_bar = gui::Rect{\n'
        '    16,   // 1. x: left edge\n'
        '    448,  // 2. y: top edge (480 - 32)\n'
        '    608,  // 3. width (not right edge)\n'
        '    24    // 4. height (not bottom edge)\n'
        '};',
        ['These fixed numbers explain the fields; real publish() layout must recompute bounds for the current client size and reserve space for page contents.',
         'This illustration has a 16-unit left/right inset and ends at y=472, leaving 8 units below in a 480-unit client area.',
         'These numbers evaluate the retained example: y = max(0, 480 - 32) and width = max(0, 640 - 32). The two arguments to max are nested inside those individual Rect fields.',
         'Check the owning field\'s coordinate convention: group content_clip uses x/y relative to its group\'s top-left corner. It is not a client-space page_bar rectangle.',
         'Coordinates must be finite and within contract limits; extents must be nonnegative. The visible tab bar needs positive width and height. Rectangles are half-open.'],
        [ref('Complete retained Rect declaration', '@gui-boundary/include/gui/geometry.hpp',
             'struct Rect {\n    double x=0, y=0, width=0, height=0;\n'
             '    bool operator==(const Rect&) const = default;\n};'),
         ref('Retained tab-bar rectangle', '@gui-boundary/examples/application.hpp',
             'next.page_bar={16,std::max(0.0,next.client_size.height-32),std::max(0.0,next.client_size.width-32),24};'),
         ref('Group-relative clipping convention', contract,
             "// A group's optional child viewport, relative to its own top-left corner.")])

    membership = guide(
        'widget-membership', 'Widget membership: name the page and parent explicitly',
        'These are named member assignments, not positional arguments. A widget ID, page ID, and parent ID have different jobs.',
        'widget.spec.key.id = WIDGET_ID;\nwidget.spec.page = PAGE_ID;\nwidget.spec.parent = PARENT_WIDGET_ID;',
        'The uppercase words are explanatory placeholders. The filled example uses actual string literals and separate statements.',
        [
            field(1, 'spec.key.id', 'std::string', 'Unique widget ID used for lookup and event routing.', 'Empty string until assigned; supply a valid ID.', '"settings.save"'),
            field(2, 'spec.page', 'std::string', 'Declared page ID. An empty string deliberately means shared chrome.', 'Empty string', '"settings"'),
            field(3, 'spec.parent', 'std::string', 'ID of an earlier group on the same page. Empty means a root widget.', 'Empty string', '"settings.form"'),
        ],
        'Filled example: a page-owned root group and its button',
        'gui::Widget group;\n'
        'group.spec.key.id = "settings.form";\n'
        'group.spec.kind = gui::Kind::group;\n'
        'group.spec.page = "settings";\n'
        'group.spec.parent = "";  // root: no parent\n'
        '\n'
        'gui::Widget button;\n'
        'button.spec.key.id = "settings.save";  // widget ID\n'
        'button.spec.kind = gui::Kind::button;\n'
        'button.spec.page = "settings";        // page ID\n'
        'button.spec.parent = "settings.form"; // parent ID\n'
        'button.state.label = "Save settings";\n'
        '\n'
        'view_.widgets.push_back(group);   // parent first\n'
        'view_.widgets.push_back(button);  // child second',
        ['Illustrative relationship only: declare the settings page first. The application recipe implements this mapping in ViewDefinition/add() instead of adding an unrelated second creation path.',
         'The current ViewDefinition has no page or parent fields. Extend that schema explicitly before trying to use definition.page or definition.parent.',
         'The group and button must have the same page. Layout still supplies their bounds; membership alone does not place them.',
         'Do not infer membership from the settings. prefix. The three string assignments establish it.'],
        [ref('Retained widget identity', contract, 'struct WidgetKey {\n    std::string id;\n    std::uint64_t generation=1;'),
         ref('Retained named membership fields', contract, '    std::string page,parent,binding;'),
         ref('Retained same-page parent rule', contract,
             'require(found->second->spec.page==s.page,"Child and parent must use the same page");')])

    sources = guide(
        'target-sources', 'target_sources: target, visibility, then source paths',
        'This CMake command appends files to an existing target. It uses whitespace-separated arguments, not C++ commas.',
        'target_sources(TARGET PRIVATE SOURCE_PATH [MORE_SOURCE_PATHS...])',
        'Reading notation: TARGET and SOURCE_PATH are placeholders; square brackets mean additional optional paths. PRIVATE is the literal keyword used by this recipe.',
        [
            field(1, 'TARGET', 'existing CMake target name', 'The target whose implementation will compile this file.', 'Required for this recipe', 'foundation_gui_application'),
            field(2, 'PRIVATE', 'literal scope keyword', 'Adds implementation sources to this target without publishing them as consumer interface sources.', 'Required scope keyword', 'PRIVATE'),
            field('3+', 'SOURCE_PATH', 'one or more paths', 'Paths relative to this CMake directory in this example. Each additional file is a separate argument.', 'At least one path in this recipe', 'shared/custom_widget.cpp'),
        ],
        'Filled example: add one shared GUI source file',
        '# In gui/CMakeLists.txt, after the target is declared:\n'
        'target_sources(\n'
        '    foundation_gui_application  # 1. existing target\n'
        '    PRIVATE                     # 2. scope\n'
        '    shared/custom_widget.cpp    # 3. source path\n'
        ')',
        ['This is an alternative to adding the file to the existing add_library source list; do not add the same file using both recipes.',
         'The example assumes the new file exists at gui/shared/custom_widget.cpp. Root CMakeLists.txt uses paths relative to the project root instead.',
         'An extra method in an already compiled .cpp needs no target_sources call. The documentation generator never runs this example or CMake.'],
        [ref('Existing target_sources use', 'gui/CMakeLists.txt',
             'target_sources(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/hosts/windows_gui_entry.cpp")'),
         ref('Shared GUI target declaration', 'gui/CMakeLists.txt',
             'add_library(foundation_gui_application STATIC shared/application.cpp ${foundation_task_executor})')])
    return {item['id']: item for item in (view, page, rect, membership, sources)}


GUIDE_LINKS = {
    ('widget', 'widget-row'): ['view-definition'],
    ('widget-placement', 'table-order'): ['view-definition'],
    ('widget-placement', 'custom-layout'): ['rect'],
    ('widget-placement', 'compose-bounds'): ['rect'],
    ('widget-placement', 'choose-page'): ['widget-membership'],
    ('tabs', 'declare-pages'): ['page'],
    ('tabs', 'declare-page-content'): ['view-definition', 'widget-membership'],
    ('tabs', 'copy-membership'): ['widget-membership'],
    ('tabs', 'page-layout'): ['rect'],
    ('source-files', 'core-cpp'): ['target-sources'],
    ('source-files', 'gui-cpp'): ['target-sources'],
    ('source-files', 'cli-cpp'): ['target-sources'],
    ('source-files', 'host-cpp'): ['target-sources'],
}
