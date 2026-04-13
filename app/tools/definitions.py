from gigachat.models import Function, FunctionParameters
from gigachat.models.chat import FunctionParametersProperty

# Список всех инструментов, доступных AI.
# Каждый инструмент — это Function, которую GigaChat может вызвать в ходе диалога.

EXECUTE_1C_QUERY = Function(
    name="execute_1c_query",
    description=(
        "Выполняет запрос на языке запросов 1С к подключённой базе данных 1С УНФ 3.0. "
        "Используй этот инструмент когда для ответа на вопрос пользователя нужны актуальные данные: "
        "продажи, остатки товаров, задолженности, финансовые показатели и т.п. "
        "Возвращает данные в формате JSON."
    ),
    parameters=FunctionParameters(
        type="object",
        properties={
            "query_text": FunctionParametersProperty(
                type="string",
                description=(
                    "Текст запроса на языке запросов 1С. "
                    "Пример: 'ВЫБРАТЬ Номенклатура, КоличествоОстаток ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки()'"
                ),
            )
        },
        required=["query_text"],
    ),
)

# Все инструменты одним списком — передаётся в Chat(functions=ALL_TOOLS)
ALL_TOOLS: list[Function] = [EXECUTE_1C_QUERY]
