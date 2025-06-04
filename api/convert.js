const ffmpegPath = require('ffmpeg-static');
const { spawn } = require('child_process');
const fs = require('fs');

module.exports = async (req, res) => {
  const chunks = [];
  req.on('data', chunk => chunks.push(chunk));
  req.on('end', () => {
    const inputBuffer = Buffer.concat(chunks);
    fs.writeFileSync('/tmp/input.webm', inputBuffer);

    const ffmpeg = spawn(ffmpegPath, [
      '-i', '/tmp/input.webm',
      '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', '24000', '-ac', '1',
      '/tmp/output.pcm'
    ]);

    ffmpeg.on('close', (code) => {
      if (code === 0) {
        const output = fs.readFileSync('/tmp/output.pcm');
        res.setHeader('Content-Type', 'audio/L16');
        res.send(output);
      } else {
        res.status(500).send('ffmpeg 변환 실패');
      }
    });
  });
}; 