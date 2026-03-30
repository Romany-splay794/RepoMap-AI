;;; RepoMap Java tree-sitter query
;;; Extracts: classes, interfaces, methods, constructors, imports, calls, annotations.

;;; ─── Class declarations ─────────────────────────────────────────────────────
(class_declaration
  name: (identifier) @def.class.name
  superclass: (superclass)? @def.class.bases
  interfaces: (super_interfaces)? @def.class.interfaces) @def.class

;;; ─── Interface declarations ─────────────────────────────────────────────────
(interface_declaration
  name: (identifier) @def.interface.name) @def.interface

;;; ─── Method declarations ────────────────────────────────────────────────────
(method_declaration
  name: (identifier) @def.method.name
  parameters: (formal_parameters) @def.method.params
  type: (_)? @def.method.return_type) @def.method

;;; ─── Constructor declarations ───────────────────────────────────────────────
(constructor_declaration
  name: (identifier) @def.method.name
  parameters: (formal_parameters) @def.method.params) @def.method

;;; ─── Annotations (decorators) ───────────────────────────────────────────────
(marker_annotation
  name: (identifier) @def.function.decorator.name) @def.function.decorator

(annotation
  name: (identifier) @def.function.decorator.name) @def.function.decorator

;;; ─── Import declarations ────────────────────────────────────────────────────
(import_declaration
  (scoped_identifier) @ref.import.module) @ref.import

;;; ─── Function call references ───────────────────────────────────────────────
(method_invocation
  name: (identifier) @ref.call.name) @ref.call.simple

(method_invocation
  object: (_) @ref.call.object
  name: (identifier) @ref.call.name) @ref.call.attr

;;; ─── Object creation ────────────────────────────────────────────────────────
(object_creation_expression
  type: (type_identifier) @ref.new.name) @ref.new
