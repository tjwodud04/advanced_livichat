document.addEventListener('DOMContentLoaded', () => {
    // 카드에 호버 효과 추가
    const cards = document.querySelectorAll('.card');

    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-10px)';
            card.style.transition = 'transform 0.3s ease';
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
        });
    });

    // 페이지 로드 시 페이드인 효과
    document.querySelector('.main-container').style.opacity = '0';
    setTimeout(() => {
        document.querySelector('.main-container').style.opacity = '1';
        document.querySelector('.main-container').style.transition = 'opacity 0.5s ease';
    }, 100);

    const modal = document.getElementById('apiKeyModal');
    const setApiKeyBtn = document.getElementById('setApiKeyBtn');
    const closeModal = document.getElementById('closeModal');
    const saveApiKey = document.getElementById('saveApiKey');
    const apiKeyInput = document.getElementById('apiKeyInput');

    // 저장된 API 키가 있는지 확인
    function getSavedApiKey() {
        return localStorage.getItem('openai_api_key');
    }
    function setSavedApiKey(key) {
        localStorage.setItem('openai_api_key', key);
    }
    let savedApiKey = getSavedApiKey();
    if (savedApiKey) {
        setApiKeyBtn.textContent = 'API 키 변경';
    }

    // 모달 열기
    setApiKeyBtn.addEventListener('click', function() {
        modal.style.display = 'block';
        savedApiKey = getSavedApiKey();
        if (savedApiKey) {
            apiKeyInput.value = savedApiKey;
        } else {
            apiKeyInput.value = '';
        }
    });

    // 모달 닫기
    closeModal.addEventListener('click', function() {
        modal.style.display = 'none';
    });

    // API 키 저장
    saveApiKey.addEventListener('click', function() {
        const apiKey = apiKeyInput.value.trim();
        if (apiKey && apiKey.startsWith('sk-')) {
            setSavedApiKey(apiKey);
            setApiKeyBtn.textContent = 'API 키 변경';
            modal.style.display = 'none';
        } else {
            alert('올바른 OpenAI API 키를 입력해주세요.');
        }
    });

    // 모달 외부 클릭 시 닫기
    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });

    // 캐릭터 선택 시 API 키 확인
    const characterLinks = document.querySelectorAll('.card:not(.disabled)');
    characterLinks.forEach(link => {
        link.addEventListener('click', function(event) {
            if (!getSavedApiKey()) {
                event.preventDefault();
                alert('대화를 시작하기 전에 OpenAI API 키를 설정해주세요.');
                modal.style.display = 'block';
            }
        });
    });
});