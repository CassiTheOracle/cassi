"""Closed catalog for the one CassiFI regional field computer.

Every entry is a stateless bounded operation over field-resident typed data.
The catalog carries no adaptive state and has no legacy solver fallback.
"""
from __future__ import annotations

from cassi_alias_cut_field import (
    REGIONAL_KERNEL_MAX_WORK as ALIAS_CUT_MAX_WORK,
    REGIONAL_STATE_SCHEMA as ALIAS_CUT_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as ALIAS_CUT_NAME,
    regional_kernel as alias_cut_kernel,
)
from cassi_alias_exact_one_field import (
    REGIONAL_KERNEL_MAX_WORK as ALIAS_EXACT_MAX_WORK,
    REGIONAL_STATE_SCHEMA as ALIAS_EXACT_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as ALIAS_EXACT_NAME,
    regional_kernel as alias_exact_kernel,
)
from cassi_alias_obstruction import (
    REGIONAL_KERNEL_MAX_WORK as ALIAS_OBSTRUCTION_MAX_WORK,
    REGIONAL_STATE_SCHEMA as ALIAS_OBSTRUCTION_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as ALIAS_OBSTRUCTION_NAME,
    regional_kernel as alias_obstruction_kernel,
)
from cassi_clause_field import (
    REGIONAL_KERNEL_MAX_WORK as CLAUSE_MAX_WORK,
    REGIONAL_STATE_SCHEMA as CLAUSE_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as CLAUSE_NAME,
    regional_kernel as clause_kernel,
)
from cassi_field_atlas import (
    REGIONAL_KERNEL_MAX_WORK as ATLAS_MAX_WORK,
    REGIONAL_STATE_SCHEMA as ATLAS_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as ATLAS_NAME,
    regional_kernel as atlas_kernel,
)
from cassi_field_cognition import (
    MECHANISM_STATE_SCHEMA,
    MECHANISM_STEP_KERNEL,
    MECHANISM_STEP_MAX_WORK,
    REGIONAL_KERNEL_MAX_WORK as COGNITION_MAX_WORK,
    REGIONAL_KERNEL_NAME as COGNITION_NAME,
    REGIONAL_STATE_SCHEMA as COGNITION_STATE_SCHEMA,
    SEMANTIC_STATE_SCHEMA,
    mechanism_step_kernel,
    regional_kernel as cognition_kernel,
)
from cassi_computation_policy import (
    REGIONAL_KERNEL_MAX_WORK as POLICY_MAX_WORK,
    REGIONAL_STATE_SCHEMA as POLICY_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as POLICY_NAME,
    regional_kernel as policy_kernel,
)
from cassi_constraint_field import (
    REGIONAL_KERNEL_MAX_WORK as CONSTRAINT_MAX_WORK,
    REGIONAL_STATE_SCHEMA as CONSTRAINT_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as CONSTRAINT_NAME,
    regional_kernel as constraint_kernel,
)
from cassi_constraint_implication import (
    REGIONAL_KERNEL_MAX_WORK as IMPLICATION_MAX_WORK,
    REGIONAL_STATE_SCHEMA as IMPLICATION_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as IMPLICATION_NAME,
    regional_kernel as implication_kernel,
)
from cassi_cubic_reduction import (
    REGIONAL_KERNEL_MAX_WORK as CUBIC_MAX_WORK,
    REGIONAL_STATE_SCHEMA as CUBIC_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as CUBIC_NAME,
    regional_kernel as cubic_kernel,
)
from cassi_field_program import (
    SCALAR_PROCEDURE_KERNEL,
    SCALAR_REGIONAL_KERNEL,
    SCALAR_REGIONAL_MAX_WORK,
    SCALAR_REGIONAL_STATE_SCHEMA,
    scalar_procedure_regional_kernel,
    scalar_regional_kernel,
)
from cassi_field_transceiver import (
    REGIONAL_KERNEL_MAX_WORK as TRANSCEIVER_MAX_WORK,
    REGIONAL_STATE_SCHEMA as TRANSCEIVER_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as TRANSCEIVER_NAME,
    regional_kernel as transceiver_kernel,
)
from cassi_field_regions import KernelCatalog
from programs.model.kernel import (
    REGIONAL_KERNEL_MAX_WORK as MODEL_MAX_WORK,
    REGIONAL_KERNEL_NAME as MODEL_NAME,
    REGIONAL_STATE_SCHEMA as MODEL_STATE_SCHEMA,
    regional_kernel as model_kernel,
)
from programs.python.kernel import (
    REGIONAL_KERNEL_MAX_WORK as PYTHON_MAX_WORK,
    REGIONAL_KERNEL_NAME as PYTHON_NAME,
    REGIONAL_STATE_SCHEMA as PYTHON_STATE_SCHEMA,
    regional_kernel as python_kernel,
)
from programs.runtime.kernel import (
    REGIONAL_KERNEL_MAX_WORK as PROGRAM_RUNTIME_MAX_WORK,
    REGIONAL_KERNEL_NAME as PROGRAM_RUNTIME_NAME,
    REGIONAL_STATE_SCHEMA as PROGRAM_RUNTIME_STATE_SCHEMA,
    regional_kernel as program_runtime_kernel,
)
from programs.workspace.kernel import (
    REGIONAL_KERNEL_MAX_WORK as WORKSPACE_MAX_WORK,
    REGIONAL_KERNEL_NAME as WORKSPACE_NAME,
    REGIONAL_STATE_SCHEMA as WORKSPACE_STATE_SCHEMA,
    regional_kernel as workspace_kernel,
)
from cassi_general_matched_field import (
    REGIONAL_KERNEL_MAX_WORK as MATCHED_MAX_WORK,
    REGIONAL_STATE_SCHEMA as MATCHED_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as MATCHED_NAME,
    regional_kernel as matched_kernel,
)
from cassi_temporal_inquiry import (
    REGIONAL_KERNEL_MAX_WORK as INQUIRY_MAX_WORK,
    REGIONAL_STATE_SCHEMA as INQUIRY_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as INQUIRY_NAME,
    regional_kernel as inquiry_kernel,
)
from cassi_hybrid_inference import (
    REGIONAL_KERNEL_MAX_WORK as HYBRID_MAX_WORK,
    REGIONAL_STATE_SCHEMA as HYBRID_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as HYBRID_NAME,
    regional_kernel as hybrid_kernel,
)
from cassi_mixed_exact_one_field import (
    REGIONAL_KERNEL_MAX_WORK as MIXED_MAX_WORK,
    REGIONAL_STATE_SCHEMA as MIXED_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as MIXED_NAME,
    regional_kernel as mixed_kernel,
)
from cassi_resonant_field import (
    REGIONAL_KERNEL_MAX_WORK as RESONANT_MAX_WORK,
    REGIONAL_STATE_SCHEMA as RESONANT_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as RESONANT_NAME,
    regional_kernel as resonant_kernel,
)
from cassi_temporal_field import (
    REGIONAL_KERNEL_MAX_WORK as TEMPORAL_MAX_WORK,
    REGIONAL_STATE_SCHEMA as TEMPORAL_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as TEMPORAL_NAME,
    regional_kernel as temporal_kernel,
)
from cassi_variational_field import (
    REGIONAL_KERNEL_MAX_WORK as VARIATIONAL_MAX_WORK,
    REGIONAL_STATE_SCHEMA as VARIATIONAL_STATE_SCHEMA,
    REGIONAL_KERNEL_NAME as VARIATIONAL_NAME,
    regional_kernel as variational_kernel,
)

_KERNELS = {
    ALIAS_CUT_NAME: alias_cut_kernel,
    ATLAS_NAME: atlas_kernel,
    ALIAS_EXACT_NAME: alias_exact_kernel,
    ALIAS_OBSTRUCTION_NAME: alias_obstruction_kernel,
    CLAUSE_NAME: clause_kernel,
    COGNITION_NAME: cognition_kernel,
    MECHANISM_STEP_KERNEL: mechanism_step_kernel,
    CONSTRAINT_NAME: constraint_kernel,
    CUBIC_NAME: cubic_kernel,
    HYBRID_NAME: hybrid_kernel,
    IMPLICATION_NAME: implication_kernel,
    MATCHED_NAME: matched_kernel,
    INQUIRY_NAME: inquiry_kernel,
    MIXED_NAME: mixed_kernel,
    POLICY_NAME: policy_kernel,
    MODEL_NAME: model_kernel,
    PYTHON_NAME: python_kernel,
    PROGRAM_RUNTIME_NAME: program_runtime_kernel,
    SCALAR_PROCEDURE_KERNEL: scalar_procedure_regional_kernel,
    RESONANT_NAME: resonant_kernel,
    SCALAR_REGIONAL_KERNEL: scalar_regional_kernel,
    TEMPORAL_NAME: temporal_kernel,
    TRANSCEIVER_NAME: transceiver_kernel,
    WORKSPACE_NAME: workspace_kernel,
    VARIATIONAL_NAME: variational_kernel,
}

# A one-work primitive makes public transition budgets, pause points, fairness,
# and replay ledgers exact even when a family can safely batch more work.
_MAX_WORK = {
    ALIAS_CUT_NAME: min(1, ALIAS_CUT_MAX_WORK),
    ATLAS_NAME: min(1, ATLAS_MAX_WORK),
    ALIAS_EXACT_NAME: min(1, ALIAS_EXACT_MAX_WORK),
    ALIAS_OBSTRUCTION_NAME: min(1, ALIAS_OBSTRUCTION_MAX_WORK),
    CLAUSE_NAME: min(1, CLAUSE_MAX_WORK),
    COGNITION_NAME: min(1, COGNITION_MAX_WORK),
    MECHANISM_STEP_KERNEL: min(1, MECHANISM_STEP_MAX_WORK),
    CONSTRAINT_NAME: min(1, CONSTRAINT_MAX_WORK),
    CUBIC_NAME: min(1, CUBIC_MAX_WORK),
    HYBRID_NAME: min(1, HYBRID_MAX_WORK),
    IMPLICATION_NAME: min(1, IMPLICATION_MAX_WORK),
    MATCHED_NAME: min(1, MATCHED_MAX_WORK),
    INQUIRY_NAME: min(1, INQUIRY_MAX_WORK),
    MIXED_NAME: min(1, MIXED_MAX_WORK),
    POLICY_NAME: min(1, POLICY_MAX_WORK),
    MODEL_NAME: min(32, MODEL_MAX_WORK),
    PYTHON_NAME: min(32, PYTHON_MAX_WORK),
    PROGRAM_RUNTIME_NAME: min(32, PROGRAM_RUNTIME_MAX_WORK),
    SCALAR_PROCEDURE_KERNEL: min(32, SCALAR_REGIONAL_MAX_WORK),
    RESONANT_NAME: min(1, RESONANT_MAX_WORK),
    SCALAR_REGIONAL_KERNEL: min(32, SCALAR_REGIONAL_MAX_WORK),
    TEMPORAL_NAME: min(1, TEMPORAL_MAX_WORK),
    TRANSCEIVER_NAME: min(1, TRANSCEIVER_MAX_WORK),
    VARIATIONAL_NAME: min(1, VARIATIONAL_MAX_WORK),
    WORKSPACE_NAME: min(1, WORKSPACE_MAX_WORK),
}

_STATE_SCHEMAS = {
    ALIAS_CUT_NAME: (ALIAS_CUT_STATE_SCHEMA,),
    ALIAS_EXACT_NAME: (ALIAS_EXACT_STATE_SCHEMA,),
    ALIAS_OBSTRUCTION_NAME: (ALIAS_OBSTRUCTION_STATE_SCHEMA,),
    ATLAS_NAME: (ATLAS_STATE_SCHEMA,),
    CLAUSE_NAME: (CLAUSE_STATE_SCHEMA,),
    COGNITION_NAME: (
        COGNITION_STATE_SCHEMA,
        SEMANTIC_STATE_SCHEMA,
    ),
    CONSTRAINT_NAME: (CONSTRAINT_STATE_SCHEMA,),
    CUBIC_NAME: (CUBIC_STATE_SCHEMA,),
    HYBRID_NAME: (HYBRID_STATE_SCHEMA,),
    IMPLICATION_NAME: (IMPLICATION_STATE_SCHEMA,),
    INQUIRY_NAME: (INQUIRY_STATE_SCHEMA,),
    MATCHED_NAME: (MATCHED_STATE_SCHEMA,),
    MECHANISM_STEP_KERNEL: (MECHANISM_STATE_SCHEMA,),
    MIXED_NAME: (MIXED_STATE_SCHEMA,),
    POLICY_NAME: (POLICY_STATE_SCHEMA,),
    MODEL_NAME: (MODEL_STATE_SCHEMA,),
    PYTHON_NAME: (PYTHON_STATE_SCHEMA,),
    PROGRAM_RUNTIME_NAME: (PROGRAM_RUNTIME_STATE_SCHEMA,),
    RESONANT_NAME: (RESONANT_STATE_SCHEMA,),
    SCALAR_PROCEDURE_KERNEL: (SCALAR_REGIONAL_STATE_SCHEMA,),
    SCALAR_REGIONAL_KERNEL: (SCALAR_REGIONAL_STATE_SCHEMA,),
    TEMPORAL_NAME: (TEMPORAL_STATE_SCHEMA,),
    TRANSCEIVER_NAME: (TRANSCEIVER_STATE_SCHEMA,),
    VARIATIONAL_NAME: (VARIATIONAL_STATE_SCHEMA,),
    WORKSPACE_NAME: (WORKSPACE_STATE_SCHEMA,),
}
if set(_STATE_SCHEMAS) != set(_KERNELS):
    raise RuntimeError("regional kernel state schemas are incomplete")

_CONTRACTS = {
    name: {
        "read_capabilities": ["arguments", "state"],
        "state_schemas": sorted(set(_STATE_SCHEMAS[name])),
        "type_name": f"{name}.state",
        "write_capabilities": ["state"],
    }
    for name in sorted(_KERNELS)
}


STANDARD_KERNEL_CATALOG = KernelCatalog(_KERNELS, _MAX_WORK, _CONTRACTS)

__all__ = ["STANDARD_KERNEL_CATALOG"]
