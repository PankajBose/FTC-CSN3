package csn.solr.morphline.processor;

import org.kitesdk.morphline.api.Record;

public abstract class IProcessor {
    private String processorName;

    public String getProcessorName() {
        return processorName;
    }

    public void setProcessorName(String processorName) {
        this.processorName = processorName;
    }

    public abstract void setParam(String paramName, String paramValue, ParamType paramType);

    public abstract void process(Record record);
}