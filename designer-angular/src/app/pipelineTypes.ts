export interface PipelineJob {
  name: string;
  source_file: string;
  extends: string[];
  stage: string;
  needs: string[];
}

export interface PipelineDocument {
    filename: string;
    stages: string[];
    jobs: Map<string, PipelineJob>;
    variables: Map<string, string>;
}
