;;; RepoMap Rust tree-sitter query
;;; Extracts: functions, impl methods, structs, enums, traits, imports, calls, attributes.

;;; ─── Top-level function definitions ─────────────────────────────────────────
(function_item
  name: (identifier) @def.function.name
  parameters: (parameters) @def.function.params
  return_type: (_)? @def.function.return_type) @def.function

;;; ─── Struct definitions ─────────────────────────────────────────────────────
(struct_item
  name: (type_identifier) @def.class.name) @def.class

;;; ─── Enum definitions ───────────────────────────────────────────────────────
(enum_item
  name: (type_identifier) @def.class.name) @def.class

;;; ─── Trait definitions ──────────────────────────────────────────────────────
(trait_item
  name: (type_identifier) @def.interface.name) @def.interface

;;; ─── Impl block methods ─────────────────────────────────────────────────────
(impl_item
  type: (type_identifier) @def.impl.type
  body: (declaration_list
    (function_item
      name: (identifier) @def.method.name
      parameters: (parameters) @def.method.params
      return_type: (_)? @def.method.return_type) @def.method))

;;; ─── Trait impl methods ─────────────────────────────────────────────────────
(impl_item
  trait: (type_identifier) @def.impl.trait
  type: (type_identifier) @def.impl.type
  body: (declaration_list
    (function_item
      name: (identifier) @def.method.name
      parameters: (parameters) @def.method.params) @def.method))

;;; ─── Attribute macros (decorators) ──────────────────────────────────────────
(attribute_item) @def.function.decorator

;;; ─── Use declarations (imports) ─────────────────────────────────────────────
(use_declaration
  argument: (_) @ref.import.module) @ref.import

;;; ─── Function call references ───────────────────────────────────────────────
(call_expression
  function: (identifier) @ref.call.name) @ref.call.simple

(call_expression
  function: (field_expression
    field: (field_identifier) @ref.call.name)) @ref.call.attr

(call_expression
  function: (scoped_identifier
    name: (identifier) @ref.call.name)) @ref.call.simple
