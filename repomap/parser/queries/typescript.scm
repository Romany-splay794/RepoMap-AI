;;; RepoMap TypeScript/JavaScript tree-sitter query
;;; Extracts: functions, arrow functions, classes, methods, interfaces,
;;;           type aliases, imports, exports, calls, new expressions.

;;; ─── Function declarations ───────────────────────────────────────────────────
(function_declaration
  name: (identifier) @def.function.name
  parameters: (formal_parameters) @def.function.params
  return_type: (type_annotation)? @def.function.return_type) @def.function

;;; ─── Arrow functions assigned to const/let/var ───────────────────────────────
(variable_declarator
  name: (identifier) @def.function.name
  value: (arrow_function
    parameters: (formal_parameters) @def.function.params)) @def.function.arrow

(variable_declarator
  name: (identifier) @def.function.name
  value: (arrow_function
    parameter: (identifier) @def.function.params)) @def.function.arrow.single

;;; ─── Class declarations ───────────────────────────────────────────────────────
(class_declaration
  name: (type_identifier) @def.class.name
  body: (class_body) @def.class.body) @def.class

;;; ─── Method definitions ───────────────────────────────────────────────────────
(method_definition
  name: (property_identifier) @def.method.name
  parameters: (formal_parameters) @def.method.params
  return_type: (type_annotation)? @def.method.return_type) @def.method

;;; ─── Interface declarations ───────────────────────────────────────────────────
(interface_declaration
  name: (type_identifier) @def.interface.name
  body: (interface_body) @def.interface.body) @def.interface

;;; ─── Type alias declarations ─────────────────────────────────────────────────
(type_alias_declaration
  name: (type_identifier) @def.type.name
  value: (_) @def.type.value) @def.type

;;; ─── Import statements (simple: just capture the source) ────────────────────
(import_statement
  source: (string) @ref.import.source) @ref.import

;;; ─── Import named specifiers ─────────────────────────────────────────────────
(import_statement
  (import_clause (named_imports (import_specifier name: (identifier) @ref.import.name)))
  source: (string) @ref.import.source) @ref.import.named

;;; ─── Export declarations ──────────────────────────────────────────────────────
(export_statement
  declaration: (_) @ref.export) @ref.export.stmt

;;; ─── Function call references ────────────────────────────────────────────────
(call_expression
  function: (identifier) @ref.call.name) @ref.call.simple

(call_expression
  function: (member_expression
    object: (_) @ref.call.object
    property: (property_identifier) @ref.call.name)) @ref.call.member

;;; ─── New expressions (constructor calls) ─────────────────────────────────────
(new_expression
  constructor: (identifier) @ref.new.name) @ref.new

(new_expression
  constructor: (member_expression
    property: (property_identifier) @ref.new.name)) @ref.new.member
