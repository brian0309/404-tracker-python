import csv


def tag_for_status(status: str) -> str:
    if status == "200":
        return "ok"
    if status == "404":
        return "notfound"
    if status == "ERR":
        return "error"
    if status == "Pending":
        return "pending"
    return "other"


def sort_tree_column(tree, column_name: str, reverse: bool):
    rows = [(tree.set(row_id, column_name), row_id) for row_id in tree.get_children("")]

    try:
        rows.sort(key=lambda row: int(row[0]) if row[0].isdigit() else 0, reverse=reverse)
    except ValueError:
        rows.sort(key=lambda row: row[0].lower(), reverse=reverse)

    for index, (_, row_id) in enumerate(rows):
        tree.move(row_id, "", index)

    tree.heading(column_name, command=lambda: sort_tree_column(tree, column_name, not reverse))


def save_visible_rows_to_csv(tree, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["Status", "Title", "URL", "Source"])
        for row_id in tree.get_children():
            writer.writerow(tree.item(row_id, "values"))
