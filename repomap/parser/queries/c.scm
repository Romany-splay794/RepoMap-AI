;;; RepoMap C tree-sitter query
;;; Extracts: functions, structs, includes, calls.

;;; ─── Function definitions ───────────────────────────────────────────────────
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @def.function.name
    parameters: (parameter_list) @def.function.params)) @def.function

;;; ─── Struct definitions ─────────────────────────────────────────────────────
(struct_specifier
  name: (type_identifier) @def.class.name
  body: (field_declaration_list) @def.class.body) @def.class

;;; ─── Include directives (imports) ───────────────────────────────────────────
(preproc_include
  path: (_) @ref.import.source) @ref.import

;;; ─── Function call references ───────────────────────────────────────────────
(call_expression
  function: (identifier) @ref.call.name) @ref.call.simple

(call_expression
  function: (field_expression
    field: (field_identifier) @ref.call.name)) @ref.call.attr
