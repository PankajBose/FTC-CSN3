package csn.solr.morphline.processor;

import org.kitesdk.morphline.api.Record;

import java.util.ArrayList;
import java.util.List;

public class RegexChanger extends IProcessor {
    private String changeTo;
    private String inputField;
    private String outputField;
    private String regex;

    @Override
    public void setParam(String paramName, String paramValue, ParamType paramType) {
        if (paramType != ParamType.STR) return;

        switch (paramName) {
            case "changeTo":
                changeTo = paramValue;
                break;
            case "inputField":
                inputField = paramValue;
                break;
            case "outputField":
                outputField = paramValue;
                break;
            case "regex":
                regex = paramValue;
                break;
        }
    }

    @Override
    public void process(Record record) {
        List list = record.get(inputField);
        if (list == null || list.isEmpty()) return;

        List<String> processedValues = new ArrayList<>();
        for (Object value : list) {
            if (value == null) processedValues.add(null);
            else processedValues.add(process(value.toString()));
        }

        record.removeAll(outputField);
        for (String processedValue : processedValues) {
            record.put(outputField, processedValue);
        }
    }

    private String process(String value) {
        return value.replaceAll(regex, changeTo);
    }
}