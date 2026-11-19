
import pandas as pd
import time


def clean_dataset(file_path: str, operations: dict):

    start_time = time.perf_counter()

    df = pd.read_csv(file_path)

    report = {
        "original_rows": len(df),
        "operations_applied": [],
        "rows_removed": 0,
        "missing_values_filled": 0,
        "missing_values_removed": 0,
        "columns_renamed": {},
    }

    # 1. Remove duplicate rows
    if operations.get("remove_duplicates"):

        before = len(df)

        df = df.drop_duplicates()

        removed = before - len(df)

        report["rows_removed"] += removed

        report["operations_applied"].append({
            "operation": "remove_duplicates",
            "removed_rows": removed,
        })

    # 2. Handle missing values
    missing_config = operations.get("missing_values", {})

    for column, config in missing_config.items():

        if column not in df.columns:
            raise ValueError(f"Column '{column}' does not exist")

        method = config.get("method")

        if method == "drop":

            before = len(df)

            df = df.dropna(subset=[column])

            removed = before - len(df)

            report["rows_removed"] += removed
            report["missing_values_removed"] += removed

        elif method == "fill":

            value = config.get("value")

            if value is None:
                raise ValueError(
                    f"Fill value required for '{column}'"
                )

            missing_before = int(df[column].isna().sum())

            df[column] = df[column].fillna(value)

            report["missing_values_filled"] += missing_before

        else:
            raise ValueError(
                f"Unsupported missing value method: {method}"
            )

        report["operations_applied"].append({
            "operation": "missing_values",
            "column": column,
            "method": method,
            "remaining_missing": int(df[column].isna().sum()),
        })

    # 3. Convert data types
    type_config = operations.get("convert_types", {})

    for column, dtype in type_config.items():

        if column not in df.columns:
            raise ValueError(f"Column '{column}' does not exist")

        if dtype == "datetime":
            df[column] = pd.to_datetime(
                df[column],
                errors="raise"
            )
        else:
            df[column] = df[column].astype(dtype)

        report["operations_applied"].append({
            "operation": "convert_types",
            "column": column,
            "new_type": dtype,
        })

    # 4. Rename columns
    rename_config = operations.get("rename_columns", {})

    if rename_config:

        missing_columns = set(rename_config) - set(df.columns)

        if missing_columns:
            raise ValueError(
                f"Columns not found: {missing_columns}"
            )

        new_columns = [
            rename_config.get(column, column)
            for column in df.columns
        ]

        if len(new_columns) != len(set(new_columns)):
            raise ValueError(
                "Renaming creates duplicate column names"
            )

        df = df.rename(columns=rename_config)

        report["columns_renamed"] = rename_config

        report["operations_applied"].append({
            "operation": "rename_columns",
            "mapping": rename_config,
        })

    # 5. Validate cleaned dataset
    if df.empty:
        raise ValueError(
            "Cleaning resulted in an empty dataset"
        )

    report["final_rows"] = len(df)
    report["final_columns"] = len(df.columns)

    report["remaining_missing_values"] = (
        df.isnull().sum().to_dict()
    )

    report["remaining_duplicates"] = int(
        df.duplicated().sum()
    )

    report["column_types"] = (
        df.dtypes.astype(str).to_dict()
    )

    # 6. Execution duration
    report["execution_duration"] = round(
        time.perf_counter() - start_time,
        4
    )

    return {
        "dataframe": df,
        "report": report,
    }
