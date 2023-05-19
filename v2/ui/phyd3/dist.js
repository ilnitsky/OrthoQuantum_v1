var compressor = require('node-minify');

compressor.minify({
  compressor: process.env.DEBUG ? 'no-compress' : 'gcc',
  input: 'js/phyd3.*.js',
  output: '/tmp/phyd3.min.js'
}).then(function(min) {
    compressor.minify({
      compressor: 'no-compress',
      input: ['js/*.min.js', '/tmp/phyd3.min.js'],
      output: 'dist/phyd3.min.js'
    });
});

compressor.minify({
  compressor: 'no-compress',
  input: 'css/**/*.css',
  output: 'dist/css/phyd3.css'
}).then(function(min) {
    compressor.minify({
      compressor: process.env.DEBUG ? 'no-compress' : 'csso',
      input: 'dist/css/phyd3.css',
      output: 'dist/phyd3.min.css'
    });
});

