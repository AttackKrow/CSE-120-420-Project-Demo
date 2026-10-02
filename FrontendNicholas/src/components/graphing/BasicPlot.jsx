import React from 'react';
import Plot from 'react-plotly.js';

class BasicPlot extends React.Component {
  render() {
    return (
      <Plot
        data={[
          {
            x: [1, 2, 3],
            y: [2, 6, 3],
            type: 'scatter',
            mode: 'lines+markers',
            marker: {color: 'red'},
          },
          {type: 'bar', x: [1, 2, 3], y: [2, 5, 3]},
        ]}
        config={{scrollZoom: true, responsive: true}}
        layout={{autosize: true, title: {text: 'A Fancy Plot'}} }
        useResizeHandler={true}
        style={{ width: '100%', height: '100%' }}
        
      />
    );
  }
}
export default BasicPlot;