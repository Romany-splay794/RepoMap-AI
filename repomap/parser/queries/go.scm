;;; RepoMap Go tree-sitter query
;;; Extracts: functions, methods, structs, interfaces, imports, calls.

;;; ─── Top-level function declarations ────────────────────────────────────────
(function_declaration
  name: (identifier) @def.function.name
  parameters: (parameter_list) @def.function.params
  result: (_)? @def.function.return_type) @def.function

;;; ─── Method declarations (receiver methods) ─────────────────────────────────
(method_declaration
  receiver: (parameter_list) @def.method.receiver
  name: (field_identifier) @def.method.name
  parameters: (parameter_list) @def.method.params
  result: (_)? @def.method.return_type) @def.method

;;; ─── Struct type declarations ───────────────────────────────────────────────
(type_declaration
  (type_spec
    name: (type_identifier) @def.class.name
    type: (struct_type) @def.class.body)) @def.class

;;; ─── Interface type declarations ────────────────────────────────────────────
(type_declaration
  (type_spec
    name: (type_identifier) @def.interface.name
    type: (interface_type) @def.interface.body)) @def.interface

;;; ─── Import declarations ────────────────────────────────────────────────────
(import_declaration
  (import_spec
    path: (interpreted_string_literal) @ref.import.source)) @ref.import

;;; ─── Function call references ───────────────────────────────────────────────
(call_expression
  function: (identifier) @ref.call.name) @ref.call.simple

(call_expression
  function: (selector_expression
    field: (field_identifier) @ref.call.name)) @ref.call.attr
