import {interval, Observable} from 'rxjs';
import {Component, OnInit, ViewChild, AfterViewChecked, ElementRef, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';

export interface PipelineJob {
  name: string;
}

export interface PipelineDocument {
  jobs: PipelineJob[];
}

@Component({
  selector: 'app-pipeline',
  templateUrl: './pipeline.component.html',
  styleUrls: ['./pipeline.component.css']
})
@Injectable()
export class PipelineComponent implements OnInit {

  private timer: Observable<number>;

  constructor(private http: HttpClient) {

  }

  pollPipeline(): void {
    const resp = this.http.get('/api/pipeline', {observe: 'body', responseType: 'json'});
    resp.subscribe(

    );
  }

  ngOnInit(): void {
    this.timer = interval(2000);
    this.timer.subscribe(n => {
      this.pollPipeline();
    });
  }

}
