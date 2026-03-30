;;; RepoMap C++ tree-sitter query
;;; Extracts: functions, classes, structs, namespaces, methods, includes, calls.

;;; ─── Function definitions ───────────────────────────────────────────────────
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @def.function.name
    parameters: (parameter_list) @def.function.params)) @def.function

;;; ─── Qualified function definitions (namespace::func or Class::method) ──────
(function_definition
  declarator: (function_declarator
    declarator: (qualified_identifier
      name: (identifier) @def.function.name)
    parameters: (parameter_list) @def.function.params)) @def.function

;;; ─── Class definitions ──────────────────────────────────────────────────────
(class_specifier
  name: (type_identifier) @def.class.name
  body: (field_declaration_list) @def.class.body) @def.class

;;; ─── Struct definitions ─────────────────────────────────────────────────────
(struct_specifier
  name: (type_identifier) @def.class.name
  body: (field_declaration_list) @def.class.body) @def.class

;;; ─── Namespace definitions ──────────────────────────────────────────────────
(namespace_definition
  name: (namespace_identifier) @def.namespace.name
  body: (declaration_list) @def.namespace.body) @def.namespace

;;; ─── Method definitions inside class body ───────────────────────────────────
(class_specifier
  body: (field_declaration_list
    (function_definition
      declarator: (function_declarator
        declarator: (field_identifier) @def.method.name
        parameters: (parameter_list) @def.method.params)) @def.method))

;;; ─── Include directives (imports) ───────────────────────────────────────────
(preproc_include
  path: (_) @ref.import.source) @ref.import

;;; ─── Function call references ───────────────────────────────────────────────
(call_expression
  function: (identifier) @ref.call.name) @ref.call.simple

(call_expression
  function: (field_expression
    field: (field_identifier) @ref.call.name)) @ref.call.attr

(call_expression
  function: (qualified_identifier
    name: (identifier) @ref.call.name)) @ref.call.simple
